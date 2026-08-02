# Hermes MCP 工具渐进式披露方案

> 源码位置：`tools/tool_search.py`、`model_tools.py`

## 1. 核心问题

每个 MCP server 可能注册几十到几千个工具（如 Cloudflare 有 3320 个），每个工具的 JSON schema 都会作为 `tools` 数组的一部分发送给模型。830 个工具 ≈ 165K tokens，直接塞进 context 会：

- 大量消耗 context window
- 每次 API 调用都重复发送（prompt caching 失效时成本倍增）
- 模型在大量工具中选择困难

## 2. 解决思路

用 **Progressive Tool Disclosure（渐进式工具披露）** 替代全量加载：

- 核心工具（terminal、read_file 等）：始终完整加载，永不 defer
- MCP/plugin 工具：schema 从 tools 数组中移除，替换为 3 个 **bridge tools**

模型需要调用某个 MCP 工具时，通过 bridge tools 按需发现和调用。

## 3. 三个 Bridge Tools

### 3.1 tool_search

BM25 关键词搜索，返回匹配的工具列表。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✅ | 搜索关键词 |
| limit | integer | ❌ | 最大返回数，默认 5，上限 20 |

**返回结构：**
```json
{
  "query": "github issue",
  "total_available": 3389,
  "matches": [
    {
      "name": "mcp-github_create_issue",
      "source": "mcp",
      "source_name": "mcp-github",
      "description": "Create a new issue in a repository..."
    }
  ]
}
```

**索引内容：** 工具名（snake_case 拆词）+ description + 顶层参数名，三者拼接为一个扁平字符串统一 tokenize，无字段级加权。

**BM25 参数：** `k1=1.5, b=0.75`（标准实现）。当 BM25 无命中时，降级为 name 子串匹配。

### 3.2 tool_describe

根据工具名返回完整 JSON schema。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 精确的工具名 |

**返回：** `{name, description, parameters}` 完整 schema。

**守卫：** 必须是 deferrable 工具（MCP/plugin），核心工具直接拒绝。

### 3.3 tool_call

通过 bridge 调用底层工具，走完整的 `handle_function_call` 流程（包括 hooks、approval、truncation）。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 精确的工具名 |
| arguments | object | ✅ | 匹配该工具 schema 的参数 |

**Probe-validation：** 模型盲调（跳过 tool_describe）时，如果缺少 required 参数，不实际调用，直接返回参数 schema + hint，让模型一轮修复，避免廉价模型反复盲试直到迭代预算耗尽。

**典型调用链：**
```
tool_search("github issue")
  → [{name: "mcp-github_create_issue", ...}]

tool_describe("mcp-github_create_issue")
  → {name, description, parameters: {...}}

tool_call("mcp-github_create_issue", {title: "...", body: "..."})
  → 实际执行结果
```

模型如果已经在 listing 中看到了精确工具名，可以跳过 tool_search，直接 tool_describe → tool_call。

## 4. 激活策略

```python
def should_activate(config, deferrable_tokens, context_length):
    if config.enabled == "off":
        return False
    if deferrable_tokens <= 0:
        return False
    return True  # 只要有任何 MCP/plugin 工具就激活
```

**只要存在 MCP/plugin 工具，bridge 就激活**，不看 token 数量。阈值不再控制激活，只控制 listing 的降级行为。

> 这是 July 2026 的设计变更。旧设计是 deferrable tokens 超过 context 的 X% 才激活，现在改为一律激活。

## 5. 分层降级（Tiered Disclosure）

激活后，deferred 工具的目录（listing）嵌入 `tool_search` 的 description 中，根据 token budget 逐级降级：

| Tier | 条件 | listing 形式 | 说明 |
|------|------|-------------|------|
| 0 | 无 defer 工具 / tool_search off | 无 | 直接透传，不激活 |
| 1a | full listing fits budget | `full` | 每个工具一行：`- name: short description` |
| 1b | full 超预算，names-only fits | `names` | 每个工具只列名字，逗号分隔 |
| 1c | names 超，部分 server summary 后 fits | `mixed` | 大 server collapse 为摘要，小 server 保留 names |
| 2 | 全部 summary 也刚好 fits | `groups` | 每个 server 只有一行：`name (N tools)` |

降级是 **per-server** 的，从最大的 server 开始逐个 collapse，小 server 不受影响。

### Listing Token Budget

```python
budget = min(listing_max_tokens, threshold_pct% × context_length)
```

默认值：
- `threshold_pct` = 5.0（context 的 5%）
- `listing_max_tokens` = 20000（绝对上限）
- 无 context_length 时 fallback = 10,000 tokens

### 降级路径示意

```
Server: cloudflare (3320 tools), github (45 tools), linear (24 tools)
Budget: 10,000 tokens

Step 1 - full (name + desc):  ~120K tokens → 超预算
Step 2 - names-only:          ~32K tokens  → 超预算
Step 3 - collapse 最大的:
  - cloudflare → summary, github+linear → names:  ~200 tokens → fits ✓
  - 结果: mixed
```

### Listing 降级后的 description 差异

| listing_form | 附加措辞 |
|---|---|
| `full` / `names` | "If a tool name appears here, do NOT claim it is unavailable — load it with tool_describe (skip tool_search when you already see the exact name)." |
| `mixed` | 同上 + "For servers marked 'names not listed', the tools exist too — find them with tool_search before concluding anything is missing." |
| `groups` | "The servers below are connected and their tools ARE available through this bridge. For any request in these domains, search here FIRST — do not claim the capability is unavailable and do not substitute a generic tool (terminal/browser) without searching." |

措辞逐步加强：模型能看到的信息越少，prompt 越强硬地要求它去搜索而不是声称能力不可用。

## 6. 不可 defer 的工具

`toolsets._HERMES_CORE_TOOLS` 中定义的核心工具 **永不 defer**，包括 terminal、read_file、write_file、web_search、browser_navigate 等。它们始终以完整 schema 出现在 tools 数组中。

Bridge tools 自身（tool_search/tool_describe/tool_call）的 name 是保留的，不会被注册为 MCP 工具，也无法通过 tool_call 递归调用。

## 7. 配置方式

`config.yaml`：

```yaml
tools:
  tool_search:
    enabled: auto        # auto | on | off（也接受 bool）
    threshold_pct: 5.0   # listing budget = context 的百分比
    listing_max_tokens: 20000  # listing 绝对上限
    search_default_limit: 5    # tool_search 默认返回条数
    max_search_limit: 20       # tool_search 最大返回条数
    listing: auto        # auto | on | off — 控制是否嵌入目录
```

- `enabled: off` → 完全关闭，MCP 工具保持完整 schema 直接加载
- `enabled: on` → 强制开启（即使只有 1 个 MCP 工具）
- `enabled: auto` → 有 MCP 工具就开启
- `listing: off` → bridge 激活但不嵌入目录，模型只能通过 tool_search 发现工具

## 8. 设计约束

1. **无状态目录**：每次 assemble 从当前 tool-defs 重建，不存在 session-keyed catalog（避免缓存漂移导致工具丢失）
2. **Bridge 路由复用**：tool_call 走 `handle_function_call`，所有 guardrails、hooks、approval 都正常生效
3. **显示层 unwrap**：用户看到的是底层工具名（如 `mcp-github_create_issue`），不是 `tool_call`
4. **Byte-stable listing**：排序确定性（group 和 tool 都按 name 排序），跨 turn 可缓存
