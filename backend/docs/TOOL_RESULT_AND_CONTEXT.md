# 工具结果硬上限与历史上下文压缩（当前实现）

**最后核对**：2026-07-26

本文档描述对话热路径上的三层上下文治理：写入时硬上限、窗口内二次剪枝、窗口外摘要。
只改发给 LLM 的组装副本时会注明；硬上限会改写当轮 `tool` 消息 content（并可能落盘）。

## 1. 分层总览

```text
工具刚返回
  └─ Layer 1 硬上限（落盘预览 / 头尾截断 / 同轮预算）
组装历史窗口
  └─ Layer 2 非最新轮 tool_use 参数 + tool_result 剪枝
挤出窗口
  └─ Layer 3 窗口外增量 LLM 摘要 → conversation_contexts
```

| 层级 | 时机 | 主要代码 | 是否改 DB 原文 |
|------|------|----------|----------------|
| L1 | 单条工具成功返回后；并行批次结束后 | `app/utils/tool_result_hard_limit.py`、`app/agents/tool_executor.py` | 当轮 tool 消息 content 会被替换；落盘写 workspace |
| L2 | `HistoryContextService.compress_history_messages` | `app/services/chat/history_context_service.py` | 否（只改组装副本） |
| L3 | `prepare_history_messages` 窗口外摘要 | 同上 + `ContextSummaryService` | 写入 `conversation_contexts` 摘要字段 |

配置根：`settings.chat_context`（`ChatContextConfig`）。

## 2. Layer 1：工具结果硬上限

### 2.1 意图

防止单条或同轮并行工具输出把上下文打爆。Agent 模式优先落盘完整原文并返回头尾预览；普通模式或落盘失败则头尾截断且不可回读。

### 2.2 调用点与边界

- **成功路径**：`ToolExecutor.execute_single_tool` 在 MCP 调用与结果标注完成后调用 `apply_hard_limit`。
- **并行批次**：`enforce_turn_budget` 在同轮全部结果返回后，按 content 长度从大到小 `force=True` 再压，直到合计 ≤ `turn_budget_chars`。
- **异常路径**：工具失败/超时返回的错误消息 **不走** 硬上限。
- **幂等**：content 已含 `full output persisted` 或 `内容已截断` 时直接跳过。

### 2.3 行为矩阵

| 条件 | 行为 |
|------|------|
| `enabled=false` | 原样返回 |
| bare 名在 `exempt_bare_names`（默认 `read_file`） | 完全跳过，含同轮 `force` |
| `tool_overrides[tool]=0` | 跳过单条阈值；同轮预算仍可 `force` |
| `agent_mode > 0` 且有 `user_id`/`conversation_id` | 超阈值 → 写入 workspace，返回预览 + 虚拟路径 |
| 否则或落盘失败 | 超阈值 → 头尾截断，标注「无法回读完整原文」 |

落盘路径：

```text
物理：data/user_data/{user_id}/conversations/{conversation_id}/workspace/{persist_subdir}/{tool_call_id}.txt
虚拟：/mnt/user-data/workspace/{persist_subdir}/{tool_call_id}.txt
```

默认 `persist_subdir=.tool-results`。预览提示 Agent 用 `read_file`（可带 offset/limit）回读。

### 2.4 默认配置

环境变量用 `__` 嵌套，例如 `CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__MAX_CHARS=30000`。

| 字段 | 默认 | 说明 |
|------|-----:|------|
| `enabled` | `true` | 总开关 |
| `max_chars` | `30000` | 单条默认上限（字符） |
| `turn_budget_chars` | `80000` | 同轮全部 tool content 合计上限；`0` 关闭预算 |
| `preview_head_chars` / `preview_tail_chars` | `2000` / `1000` | 预览/截断保留头尾 |
| `persist_subdir` | `.tool-results` | 相对 workspace |
| `exempt_bare_names` | `["read_file"]` | 全量豁免，防 persist↔read 循环 |
| `tool_overrides` | 见下 | 覆盖单条阈值 |

默认 `tool_overrides`：

| 工具 bare 名 | 上限 | 含义 |
|---|---:|---|
| `exec` | 20000 | shell 命令输出 |
| `search_files` | 20000 | 搜索结果 |
| `web_site_crawl` | 20000 | 站点爬取 |
| `web_pages_extract` | 25000 | 页面抽取 |
| `load_skill` | 0 | 关闭该工具单条硬上限（预算仍可强制） |

键可为 LLM 可见名（如 `shell_exec`）或 bare 名（如 `exec`）。

### 2.5 与 `read_file` 的配合

`read_file` 默认在豁免列表：硬上限不会截断/落盘其返回。体积由工具自身控制——默认 `limit=2000` 行，且 `le=2000`。需要大文件时用 offset/limit 分页，而不是依赖硬上限二次截断。

### 2.6 排障

1. 日志关键字：`Tool result persisted due to hard limit` / `Tool result truncated` / `Tool result persist failed`。
2. Agent 看不到全文：检查 workspace 下 `.tool-results/` 是否存在对应 `{tool_call_id}.txt`。
3. `read_file` 仍被截断：通常是工具自身的行数 `limit`，不是硬上限。
4. 同轮多工具仍爆上下文：调低 `turn_budget_chars` 或相关 `tool_overrides`。
5. 异常工具错误特别长：异常路径不走硬上限，属预期。

## 3. Layer 2：窗口内历史剪枝

入口：`HistoryContextService.compress_history_messages`。

**边界**：只处理窗口内消息；**最新一轮**（最后一条 user + 对应 assistant，实现上 `idx >= len-2`）的 `tool_use` / `tool_result` **完整保留**。

### 3.1 非最新轮 `tool_use`

配置在 `chat_context.tool_result_compression`：

| 字段 | 默认 | 行为 |
|------|-----:|------|
| `tool_arg_max_chars` | `500` | 整段 `arguments_text` 超过才截断 |
| `tool_arg_keep_chars` | `200` | JSON 内字符串叶子保留前缀，后缀 `...[truncated]` |

流程：`json.loads` → 递归收缩过长字符串 → `json.dumps` 写回 `arguments_text` 并同步 `arguments_json`。非法 JSON **原样保留**（避免破坏参数导致 provider 400）。

### 3.2 非最新轮 `tool_result`

优先级：

1. 有非空 `summary` → 用 summary；
2. 否则 token 数 > `message_summary_threshold_tokens`（默认 2000）→ 头尾截断（约 60%/40%，见 `TokenCalculator.truncate_text_to_tokens_head_tail`）；
3. 组装副本会清空 `summary` 与 `structured_content_for_display`（避免重复占位）。

### 3.3 历史窗口尺寸

| 字段 | 默认 | 说明 |
|------|-----:|------|
| `history_window.max_rounds` | `20` | 一轮 = 一条 user + 对应 assistant（含其中 tool） |
| `history_window.token_ratio` | `0.25` | 历史 token 预算 = `context_limit * ratio` |

先按轮数切窗，再压缩，再按轮 token 预算从更早轮裁掉。

## 4. Layer 3：窗口外摘要

`window_out_summary.enabled`（默认 `true`）时：

1. 对比当前窗口外消息 id 集合与已存 `last_summarized_message_ids`；
2. 若集合相同 → 复用 `summary_before_window`；
3. 若仅增量扩大 → 对增量消息做 `summarize_merge`；
4. 否则对全部窗口外消息重新摘要；
5. 摘要写入 `conversation_contexts`，后续注入 user_context/system。

`summary_max_tokens` 默认 `1000`。摘要失败只打 warning，不阻断对话。

## 5. 相关软压缩（同轮 FAISS）

`tool_result_compression` 还控制**当轮**超长工具结果的 FAISS/摘要软压缩（`context_compactor` 等），与 L1 硬上限不同：

- 软压缩：按 token 阈值做相关性过滤/摘要，可写回 `summary`；
- 硬上限：按字符硬切，Agent 模式落盘。

`file` / `shell` server 在 `SKIP_TOOL_RESULT_COMPACTION_SERVERS` 中，跳过该软压缩（仍受 L1 硬上限约束，`read_file` 除外）。

## 6. 配置示例

```dotenv
# 硬上限
CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__ENABLED=true
CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__MAX_CHARS=30000
CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__TURN_BUDGET_CHARS=80000

# 历史窗口
CHAT_CONTEXT__HISTORY_WINDOW__MAX_ROUNDS=20
CHAT_CONTEXT__HISTORY_WINDOW__TOKEN_RATIO=0.25

# 窗口内旧轮剪枝
CHAT_CONTEXT__TOOL_RESULT_COMPRESSION__MESSAGE_SUMMARY_THRESHOLD_TOKENS=2000
CHAT_CONTEXT__TOOL_RESULT_COMPRESSION__TOOL_ARG_MAX_CHARS=500
CHAT_CONTEXT__TOOL_RESULT_COMPRESSION__TOOL_ARG_KEEP_CHARS=200

# 窗口外摘要
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__ENABLED=true
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__SUMMARY_MAX_TOKENS=1000
```

## 7. 源码索引

| 主题 | 路径 |
|------|------|
| 硬上限算法 | `app/utils/tool_result_hard_limit.py` |
| 执行器接入 | `app/agents/tool_executor.py` |
| 历史组装 | `app/services/chat/history_context_service.py` |
| 配置模型 | `app/schemas/config.py`（`ToolResultHardLimitConfig`、`ToolResultCompressionConfig`、`HistoryWindowConfig`、`WindowOutSummaryConfig`） |
| 单测 | `tests/utils/test_tool_result_hard_limit.py`、`tests/services/chat/test_history_context_service.py` |
