# 工具结果硬上限与统一上下文守卫

**最后核对**：2026-08-23

对话热路径上的上下文治理：

1. **L1 硬上限**：工具刚返回时按字符截断/落盘
2. **统一上下文守卫**：每次 LLM 调用前检查总 prompt，按需分级降级

## 1. 分层总览

```text
工具刚返回
  └─ Layer 1 硬上限（落盘预览 / 头尾截断 / 同轮预算）
每次 LLM 调用前
  └─ unified_context_guard（总 prompt 阈值）
       Step 1 未超限 → 直接放行
       Step 2 压缩全部历史 ToolResult（+ 全部历史 tool_use args）
       Step 3 动态 token 预算切窗 + 窗口外 LLM 摘要
       Step 4 size-aware 压缩当前轮工具结果（先 keep_recent，仍超则 keep_recent=0）
       Step 5 仍超限 → 停止工具调用，转 final answer
```

| 层级 | 时机 | 主要代码 | 是否改 DB 原文 |
|------|------|----------|----------------|
| L1 | 单条工具成功返回后；并行批次结束后 | `app/utils/tool_result_hard_limit.py`、`app/agents/tool_executor.py` | 当轮 tool 消息 content 会被替换；落盘写 workspace |
| 守卫 Step 2/4 | LLM 调用前 | `HistoryContextService` + `ChatSessionAgent.unified_context_guard` | 否（组装副本 / 本轮内存） |
| 守卫 Step 3 | LLM 调用前且仍超限 | 同上 + `ContextSummaryService` | 写入 `conversation_contexts` |

配置根：`settings.chat_context`（`ChatContextConfig`）。

阈值：

```text
reserved_output = min(llm.max_output_tokens, unified_guard.max_output_tokens)
context_threshold = context_limit - reserved_output - buffer_tokens
```

`llm.max_output_tokens` 来自模型元数据或按 `context_limit` 推断（见 `infer_max_output_tokens`）。

## 2. Layer 1：工具结果硬上限

### 2.1 意图

防止单条或同轮并行工具输出把上下文打爆。Agent 模式优先落盘完整原文并返回短预览（可 `read_file` 回读）；落盘失败则按 `max_chars` 头尾截断。非 Agent 模式 L1 **原样放行**，由统一上下文守卫（尤其 Step 4）按总 prompt 预算兜底。

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
| `agent_mode <= 0` | 原样返回（含同轮 turn budget）；由统一守卫兜底 |
| `agent_mode > 0` 且有 `user_id`/`conversation_id` | 超阈值 → 写入 workspace，返回 `preview_head/tail` 预览 + 虚拟路径 |
| Agent 落盘失败（非 force） | 超阈值 → 在 `max_chars` 预算内按 `preview_head:preview_tail` **比例**分配头尾后截断，标注「无法回读完整原文」 |
| Agent 落盘失败或缺 id（force） | 同轮预算强制压缩 → 直接使用 `preview_head_chars` / `preview_tail_chars` 短截断（不再按 `max_chars` 放大） |

落盘路径：

```text
物理：data/user_data/{user_id}/conversations/{conversation_id}/workspace/{persist_subdir}/{tool_call_id}.txt
虚拟：/mnt/user-data/workspace/{persist_subdir}/{tool_call_id}.txt
```

### 2.4 默认配置

环境变量用 `__` 嵌套，例如 `CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__MAX_CHARS=30000`。

| 字段 | 默认 | 说明 |
|------|-----:|------|
| `enabled` | `true` | 总开关 |
| `max_chars` | `30000` | 单条默认上限（字符）；仅 Agent |
| `turn_budget_chars` | `80000` | 同轮全部 tool content 合计上限；仅 Agent；`0` 关闭 |
| `preview_head_chars` / `preview_tail_chars` | `2000` / `1000` | Agent 落盘预览与截断回退头尾 |
| `persist_subdir` | `.tool-results` | 相对 workspace |
| `exempt_bare_names` | `["read_file"]` | 全量豁免，防 persist↔read 循环 |
| `tool_overrides` | 见下 | 覆盖单条阈值 |

默认 `tool_overrides`：`exec`/`search_files`/`web_site_crawl` 20000，`web_pages_extract` 25000，`load_skill` 0。

### 2.5 与 `read_file` 的配合

`read_file` 默认在豁免列表。体积由工具自身 `limit` 控制。

## 3. 统一上下文守卫

入口：`ChatSessionAgent.unified_context_guard`（每次工具轮 / final 轮 LLM 调用前）。

`unified_guard.enabled=false` 时跳过守卫（仅依赖 L1），打 warning。

### 3.1 Step 2：历史工具压缩

`HistoryContextService.compress_history_tool_results`：

- **所有历史轮** `ToolResultBlock`：有 `summary` 则替换 content，否则超 `message_summary_threshold_tokens` 头尾截断
- **所有历史轮** `tool_use` args：hermes 风格 JSON 叶子截断
- 只改组装副本，DB 原文不变

### 3.2 Step 3：动态窗口外摘要

```text
remaining_budget = threshold - count(system) - count(current_user) - count(tool_rounds)
in_window, out_of_window = split_history_by_token_budget(history, remaining_budget)
```

对 `out_of_window` 做增量 `summarize_merge`（结构化 9 段模板 + prior 过大时自压缩），写入 `conversation_contexts`，并从 prompt 中移除窗口外消息、注入摘要。

反抖动：连续失败 ≥ `anti_thrash_failure_threshold`（默认 3）且在 `anti_thrash_recovery_seconds`（300s）内跳过 LLM。

### 3.3 Step 4：当前轮 size-aware 压缩

将 `tool_round_messages` 按「一次 `ToolUseMessage` + 其后连续 `ToolResultMessage`」分组：

1. **先**保留最新 `keep_recent`（默认 2）组，只压缩更旧组中超 `tool_result_compress_threshold_chars` 的结果（按大小降序 head-tail，默认各 500 字符），压到阈值即停。
2. **若仍超限**，再以 `keep_recent=0` 重跑，允许压缩本轮全部（含最新）大结果。

非 Agent 依赖本步兜底单条超大工具输出（L1 已放行）。与 Agent L1 `max_chars` **不冲突**：L1 是写入/落盘上限；本项是总预算仍超时的二次压缩门闩。

### 3.4 Step 5

压缩后仍超限且允许停工具 → 强制 final answer。

## 4. 统一守卫默认配置

| 字段 | 默认 | 说明 |
|------|-----:|------|
| `unified_guard.enabled` | `true` | 总开关 |
| `buffer_tokens` | `13000` | 安全缓冲 |
| `max_output_tokens` | `8192` | 输出预留封顶 |
| `keep_recent_tool_results` | `2` | Step 4 保留最新工具组数（ToolUse + 其后 results） |
| `tool_result_compress_threshold_chars` | `1000` | Step 4 候选门闩 |
| `tool_result_compress_keep_head/tail_chars` | `500` | Step 4 截断保留 |
| `anti_thrash_failure_threshold` | `3` | 反抖动 |
| `anti_thrash_recovery_seconds` | `300` | 反抖动恢复 |

`window_out_summary.enabled` / `summary_max_tokens` 仍控制 Step 3。

已删除：`history_window.*`、`tool_round_context_limit_ratio`。

## 5. 手动全量压缩与 `last_summarized_message_ids`

侧栏「压缩会话」走 `POST /api/conversation/{id}/compress`（`HistoryContextService.compact_full_conversation`），与守卫 Step 3 **共用** `conversation_contexts`：

| 字段 | 用途 |
|------|------|
| `summary_before_window` | 注入后续 prompt 的窗口外摘要 |
| `last_summarized_message_ids` | 已摘要消息 ID；`filter_summarized_history` 会从 LLM history 剔除 |

意图：用户主动把长会话压成摘要，降低后续 turn 的前缀长度；**不删除** `messages` 行，UI 仍显示完整聊天记录。

行为：

1. 用 `summarization` 场景模型对当前全部消息（或相对已存 ID 的增量）做 `summarize_merge`。
2. 写入摘要 + UNION 后的消息 ID。
3. 下一轮 `ChatOrchestrator` 先读摘要，再过滤 history：已摘要 ID 不再进入 `_working_history`。
4. 守卫 Step 3 若再切窗：只要有 prior + delta 就增量 merge；写入 ID 做 UNION，避免把手动全量结果覆盖成子集。
5. 当前 ID 集合已全部摘要过且摘要非空 → 幂等返回，不调 LLM。
6. 存在 `pending` 助手消息 → HTTP 409。

配置仍用 `CHAT_CONTEXT__WINDOW_OUT_SUMMARY__SUMMARY_MAX_TOKENS`（默认 1000）。API 契约与网关超时见 `docs/会话管理.md`。

## 6. 相关软压缩（同轮 FAISS）

`tool_result_compression` 还控制**当轮**超长工具结果的 FAISS/摘要软压缩（`context_compactor`），与 L1 硬上限不同。`file` / `shell` 在跳过列表中。

## 7. 配置示例

```dotenv
CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__MAX_CHARS=30000
CHAT_CONTEXT__UNIFIED_GUARD__ENABLED=true
CHAT_CONTEXT__UNIFIED_GUARD__BUFFER_TOKENS=13000
CHAT_CONTEXT__UNIFIED_GUARD__MAX_OUTPUT_TOKENS=8192
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__ENABLED=true
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__SUMMARY_MAX_TOKENS=1000
```

## 8. 源码索引

| 主题 | 路径 |
|------|------|
| 硬上限 | `app/utils/tool_result_hard_limit.py` |
| 统一守卫 | `app/agents/chat_session_agent.py` |
| 压缩原语 / 手动全量压缩 | `app/services/chat/history_context_service.py`（`compact_full_conversation`、`filter_summarized_history`） |
| 压缩 API | `app/api/conversation.py` `POST /{conversation_id}/compress` |
| token 切窗 | `app/utils/history_truncate.py` |
| 摘要 | `app/services/conversation/context_summary_service.py` |
| 配置 | `UnifiedContextGuardConfig`、`ToolResultHardLimitConfig`、`WindowOutSummaryConfig` |
| 单测 | `tests/agents/test_unified_context_guard.py`、`tests/services/chat/test_history_context_service.py`、`tests/services/chat/test_conversation_compress.py` |
