---
name: MCP 工具名前缀
overview: 借鉴 DeerFlow / langchain-mcp-adapters 的「Agent 层带前缀、MCP 层裸名」双轨命名，在 MCPToolGateway 统一实现注册拼接与调用前剥离；同步更新策略、Prompt、前端展示（仅 UI 层可识别历史裸名 content block，不做 call_tool 裸名 fallback）。
todos:
  - id: tool-naming-module
    content: 新增 backend/app/mcp/tool_naming.py（拼接/剥离/匹配）及 tests/mcp/test_tool_naming.py
    status: pending
  - id: gateway-prefix
    content: 改造 MCPToolGateway：注册拼接前缀、tools_map 路由、调用前按 server 剥离裸名
    status: pending
  - id: agents-prompts
    content: 更新 tool_call_policy、tool_executor、tavily_result_processor 与 prompts 中的工具名比较与文案
    status: pending
  - id: frontend-bare-name
    content: 新增 mcpToolName 工具函数并更新 ToolBlock 相关组件（图标/结果/参数/标题）
    status: pending
  - id: docs-tests
    content: 更新 MCP_CONFIG_ANALYSIS.md，补充 gateway 集成测试并跑通 lint/test
    status: pending
isProject: false
---

# MCP 工具名 `{server_name}_` 前缀改造方案

## 与 DeerFlow 的对照与借鉴

DeerFlow 通过 `MultiServerMCPClient(tool_name_prefix=True)` 在 **LangChain/Agent 层** 使用 `{serverName}_{原始名}`，在 **`session.call_tool` 前** 剥回原始名。本项目的 `MCPToolGateway` 职责等价，可直接对齐其分阶段模型：

| 阶段 | DeerFlow | Chat Agent（本方案） |
|------|----------|----------------------|
| MCP `list_tools` | `search` | `web_search`（不变） |
| 暴露给 LLM | `github_search` | `tavily-mcp_web_search` |
| LLM tool call | `github_search` | `tavily-mcp_web_search` |
| 调用 MCP 前 | `startswith(f"{server_name}_")` 剥离 | 同上，经 `to_mcp_tool_name()` |
| `call_tool` 参数 | `search` | `web_search` |

**采纳的设计点：**

1. **前缀仅用于 Agent/LLM 层**，MCP 协议与各 Server 实现不改。
2. **`server_name` 必须等于 `mcp_servers` 配置键**（如 `tavily-mcp`），拼接与剥离都基于该 key，不用模块名或别名。
3. **调用前剥离（strip）而非长期维护 `original_tool_names` 映射表**：先由 `tools_map[llm_name]` 得到 `server_name`，再 `strip_llm_tool_name(llm_name, server_name)` → 原始名（与 DeerFlow `_make_session_pool_tool` 一致）。
4. **Best-effort 剥离**：仅当 `llm_name.startswith(f"{server_name}_")` 时剥离；否则将全名传给 MCP（用于极少数边界或调试）。

**本项目差异（保留原方案）：**

- 配置键使用 `mcp_servers` 的字面量 key（如 `tavily-mcp`、`my_custom_mcp`），前缀形如 `{key}_{tool.name}`。
- **`server_name` 可含 `-` 与 `_`**；解析归属时不依赖「第一个 `_` 切开」，而对已知 server 列表做**最长前缀匹配**（见下）。
- 前端需剥离前缀做图标/结果渲染；与后端共用同一套最长前缀逻辑（传入 server 列表时）。
- **不做裸名 fallback**：`call_tool` 仅接受 `tools_map` 中的带前缀 LLM 名；LLM 传裸名将直接报错（与 DeerFlow 一致）。

---

## 目标命名

- **LLM 可见名**：`{server_name}_{tool.name}`，例如 `tavily-mcp_web_search`、`my_custom_mcp_web_search`
- **MCP 协议调用名**：原始 `tool.name`
- **分隔符**：单下划线 `_` 连接 `{server_name}` 与 `{tool.name}`；`server_name` 为 `mcp_servers` 配置键（允许 `-`、`_` 等，与 key 字面量一致）
- **归属解析**：在已知 server 列表上，取满足 `llm_name.startswith(f"{name}_")` 的 **最长** `name`（避免 `mcp` 误匹配 `mcp_extra_tool`）

```mermaid
flowchart LR
  A["MCP list_tools<br/>web_search"] --> B["Gateway 注册<br/>tavily-mcp_web_search"]
  B --> C["LLM tool_call<br/>tavily-mcp_web_search"]
  C --> D["Gateway 剥离<br/>web_search"]
  D --> E["client.call_tool<br/>web_search"]
```

---

## 核心改动（后端）

### 1. 命名模块 [`backend/app/mcp/tool_naming.py`](backend/app/mcp/tool_naming.py)

| 函数 | 职责 | 对应 DeerFlow |
|------|------|----------------|
| `llm_tool_name(server_name, bare_name)` | `f"{server_name}_{bare_name}"` | adapter `lc_tool_name` |
| `strip_llm_tool_name(llm_name, server_name)` | `startswith` 后 `len(prefix)` 截断 | `_make_session_pool_tool` |
| `to_mcp_tool_name(llm_name, server_name)` | 包装 strip，供 gateway 调用 | 同上 |
| `is_llm_tool(llm_name, server_name, bare_name)` | 策略层比较 | — |
| `resolve_server_by_prefix(llm_name, server_names)` | 已知 key 列表上**最长前缀**匹配 `f"{name}_"` | DeerFlow 归属识别（增强） |
| `bare_tool_name(llm_name, server_names)` | 先 `resolve_server_by_prefix`，再 `strip_llm_tool_name`；无匹配则原样返回 | — |

**`resolve_server_by_prefix` 算法（后端/前端一致）：**

```python
def resolve_server_by_prefix(llm_name: str, server_names: Iterable[str]) -> str | None:
    candidates = [n for n in server_names if llm_name.startswith(f"{n}_")]
    if not candidates:
        return None
    return max(candidates, key=len)  # 最长 key 优先
```

单元测试覆盖：正常剥离、`server_name` 不匹配时不误剥、裸名、`tavily-mcp` / `my_custom_mcp`、**重叠前缀**（`mcp` vs `mcp_extra` 取更长者）。

### 2. 改造 [`backend/app/mcp/gateway.py`](backend/app/mcp/gateway.py)

**索引 `rebuild_tool_index`**

```python
llm_name = llm_tool_name(server_name, tool.name)
self.tools_map[llm_name] = server_name
```

- 跨 Server 同名冲突：前缀后天然消除；`tool_conflicts` / `keep_first_server` 可降级为断言级防御日志。
- **不再维护** `original_tool_names` 字典（改由 strip 推导，与 DeerFlow 一致）。

**`get_tools_for_llm`**

```python
"name": llm_tool_name(server_name, tool.name),
```

**`call_tool`（DeerFlow 调用前还原）**

```python
server_name = self.tools_map[llm_name]  # llm_name 为 LLM 传入
mcp_name = to_mcp_tool_name(llm_name, server_name)
await client.call_tool(mcp_name, args, ...)
```

- `llm_name not in tools_map` 时直接 `ValueError`（列出现有带前缀工具名），**不**尝试裸名解析或调用。

**`get_tool_info` / `_get_tool_input_schema`**

- 入参为 LLM 名；schema 查找时对 `tools_by_server[server_name]` 用 `to_mcp_tool_name(...)` 与 `tool.name` 比较。

### 3. Agent / Prompt / 前端

（与原计划相同，略）

- [`tool_call_policy.py`](backend/app/agents/tool_call_policy.py)、[`tool_executor.py`](backend/app/agents/tool_executor.py)、[`tavily_result_processor.py`](backend/app/agents/utils/tavily_result_processor.py)：用 `is_llm_tool(name, "tavily-mcp", "web_search")`。
- Prompt 中工具名与 LLM schema 一致（`tavily-mcp_web_search`）。
- 前端 [`frontend/src/utils/mcpToolName.ts`](frontend/src/utils/mcpToolName.ts)：
  - `resolveServerByPrefix` / `bareToolName(llmName, serverNames?)` 与后端同算法；
  - `serverNames` 有则最长前缀剥离（展示/图标）；
  - `matchesTool` 仅用于**只读展示**历史 content block 中的裸名（不参与后端路由）；
  - 若后续有会话级 MCP server 列表 API，可注入 `serverNames` 以精确展示。

### 4. 文档与测试

- 更新 [`backend/docs/MCP_CONFIG_ANALYSIS.md`](backend/docs/MCP_CONFIG_ANALYSIS.md)：增加「命名双轨」一节，对照 DeerFlow 时序图。
- `tests/mcp/test_tool_naming.py`：剥离逻辑与 DeerFlow 示例表对齐（`github` + `search` → `github_search` → `search`）。
- `tests/mcp/test_gateway_tool_names.py`：mock 双 server 同名工具，验证暴露名不同、调用均落到正确裸名。

---

## 完整时序（单次 tool call）

```
1. [注册]   MCP: web_search
2. [暴露]   LLM schema: tavily-mcp_web_search
3. [调用]   LLM 传入 tavily-mcp_web_search
4. [路由]   tools_map → server_name = tavily-mcp
5. [剥离]   to_mcp_tool_name → web_search
6. [MCP]    client.call_tool("web_search", args)
7. [持久化] content block.name 仍为 tavily-mcp_web_search（关联 tool_call_id）
```

---

## 实施顺序

1. `tool_naming.py` + 单元测试（含 DeerFlow 对照用例）
2. `gateway.py` 改造
3. Agent / Prompt
4. 前端 `mcpToolName`
5. 文档 + gateway 集成测试

---

## 风险与边界

| 要点 | 说明 |
|------|------|
| 前缀与配置强绑定 | `server_name` 必须等于 `mcp_servers` 的 key |
| 重叠 server key | 如同时存在 `mcp` 与 `mcp_extra`，依赖**最长前缀**避免误归属 |
| 工具名本身含 `_` | 已知 `server_name` 下用完整前缀 `f"{server_name}_"` 剥离，裸名可保留尾部 `_` |
| 进行中/历史会话 | 已持久化的裸名 tool block 仅前端展示可识别；**新 tool call 必须用带前缀名**，否则 gateway 报错 |
| 前端无 server 列表 | 图标/分支逻辑用 `matchesTool`；展示剥离在拿到 `serverNames` 后更精确 |

---

## 示例对照表（与 DeerFlow §8 同构）

| mcp_servers key | MCP 原始名 | LLM 可见名 | call_tool 参数 |
|-----------------|------------|------------|----------------|
| `tavily-mcp` | `web_search` | `tavily-mcp_web_search` | `web_search` |
| `my_custom_mcp` | `web_search` | `my_custom_mcp_web_search` | `web_search` |
| `file-mcp` | `read_file` | `file-mcp_read_file` | `read_file` |
| `time-mcp` | `get_current_time` | `time-mcp_get_current_time` | `get_current_time` |
