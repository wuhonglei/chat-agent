# 工具结果硬上限与统一上下文守卫

**最后核对**：2026-07-26

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
       Step 4 size-aware 压缩当前轮旧工具结果
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

将 `tool_round_messages` 按「一次 `ToolUseMessage` + 其后连续 `ToolResultMessage`」分组，保留最新 `keep_recent` 组；对其余组中 `len(content) > tool_result_compress_threshold_chars` 的 `ToolResultMessage`，按大小降序 head-tail（默认各 500 字符），达标即停。

与 L1 `max_chars` **不冲突**：L1 是写入上限；本项是总预算仍超时的二次压缩门闩。

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

## 5. 相关软压缩（同轮 FAISS）

`tool_result_compression` 还控制**当轮**超长工具结果的 FAISS/摘要软压缩（`context_compactor`），与 L1 硬上限不同。`file` / `shell` 在跳过列表中。

## 6. 配置示例

```dotenv
CHAT_CONTEXT__TOOL_RESULT_HARD_LIMIT__MAX_CHARS=30000
CHAT_CONTEXT__UNIFIED_GUARD__ENABLED=true
CHAT_CONTEXT__UNIFIED_GUARD__BUFFER_TOKENS=13000
CHAT_CONTEXT__UNIFIED_GUARD__MAX_OUTPUT_TOKENS=8192
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__ENABLED=true
CHAT_CONTEXT__WINDOW_OUT_SUMMARY__SUMMARY_MAX_TOKENS=1000
```

## 7. 源码索引

| 主题 | 路径 |
|------|------|
| 硬上限 | `app/utils/tool_result_hard_limit.py` |
| 统一守卫 | `app/agents/chat_session_agent.py` |
| 压缩原语 | `app/services/chat/history_context_service.py` |
| token 切窗 | `app/utils/history_truncate.py` |
| 摘要 | `app/services/conversation/context_summary_service.py` |
| 配置 | `UnifiedContextGuardConfig`、`ToolResultHardLimitConfig`、`WindowOutSummaryConfig` |
| 单测 | `tests/agents/test_unified_context_guard.py`、`tests/services/chat/test_history_context_service.py` |
