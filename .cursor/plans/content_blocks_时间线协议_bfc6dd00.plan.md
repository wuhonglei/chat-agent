---
name: content_blocks 时间线协议
overview: 把一次 run 的“思考/文本/工具调用/工具结果”统一为按发生顺序追加的 `content_blocks`，用于流式输出、落库与前端渲染，并用 `tool_call_id` 做 ToolUse↔ToolResult 的稳定关联。
todos:
  - id: define-block-schemas
    content: 新增后端/前端统一的 ContentBlock 类型与 ChatMessageItem.content_blocks 字段
    status: completed
  - id: streaming-aggregator
    content: 后端实现 ContentBlocksAggregator：text/thinking delta、tool_calls 分片聚合、tool_result 关联并产出 SSE
    status: completed
  - id: db-migration
    content: messages 表新增 content_blocks JSON 列，并在 update_assistant_message 落库
    status: completed
  - id: frontend-render
    content: 前端改为消费 content_block SSE 并以 contentBlocks 渲染（替换 mcp_tool_call/toolCalls timeline）
    status: completed
  - id: validation
    content: 用并行工具调用与乱序结果场景验证 time-line 与 tool_call_id 关联正确
    status: completed
isProject: false
---

# content_blocks 时间线协议（最终版）

## 目标与边界

- **目标**：后端流式输出、消息落库、前端渲染统一使用 `content_blocks: ContentBlock[]`，按发生顺序追加，完整还原一次 run 的时间线（`thinking` / `tool_use` / `tool_result` / `text` 可交织）。
- **兼容策略**：允许不兼容旧前端/旧协议；`content_blocks` 为唯一权威结构。迁移期可在服务端对旧字段做回填，确保历史可用。
- **落库策略**：在 `messages` 表新增 JSON 字段 `content_blocks`（结构清晰、可演进），并在兼容期内可由 blocks 派生旧字段 `content/reasoning/tool_calls` 供存量逻辑使用。

## 现状定位（关键点）

- **后端**：当前把最终内容拆成 `content/reasoning/tool_calls`，工具过程通过 `mcp_tool_call` 事件推送（见 `[backend/app/agents/chat_session_agent.py](backend/app/agents/chat_session_agent.py)`）。
- **tool_calls 流式聚合**：按 `delta.tool_calls[i].index` 合并，结束后转 OpenAI `tool_calls` list（见 `[backend/app/agents/utils/tool_call_stream.py](backend/app/agents/utils/tool_call_stream.py)` `merge_tool_call_deltas`）。
- **落库**：`update_assistant_message` 写 `MessageDb.tool_calls`（见 `[backend/app/services/message/message_db.py](backend/app/services/message/message_db.py)`）。
- **前端**：依赖 `mcp_tool_call` 事件 + `toolCalls` timeline（见 `[frontend/src/hooks/chat.ts](frontend/src/hooks/chat.ts)`、`[frontend/src/store/slices/chatSlice.ts](frontend/src/store/slices/chatSlice.ts)`、`AssistantMessage` 组件树）。

## 新数据模型（后端/前端一致）

- **核心字段**：`content_blocks: ContentBlock[]`
  - `TextBlock`: `{ id, type: "text", text }`
  - `ThinkingBlock`: `{ id, type: "thinking", text }`
  - `ToolUseBlock`: `{ id, type: "tool_use", tool_call_id, name, arguments_text, arguments_json? }`
  - `ToolResultBlock`: `{ id, type: "tool_result", tool_call_id, tool_use_id, is_error, content, summary? }`
- **ChatRequest 入参调整**：
  - 用户提问由原 `chat_request.content` 改为 `chat_request.content_blocks`（类型与 `ContentBlock` 定义一致）。
  - 用户输入通常是单个 `TextBlock`（例如 `{ type: "text", text: "..." }`）。
  - 用户侧 block 的 `id` **由前端生成**；后端落库与回传时原样保留该 `id`。
  - assistant 侧输出同样统一写入 `content_blocks`（`thinking/text/tool_use/tool_result`）。
- **ContentBlock.id 生成方式（run 内稳定、单调递增）**：
  - 一次 run 开始时：初始化 `block_seq = 0`
  - 每创建一个新 block 时：`block_seq += 1`，并生成 `id = f"cb_{block_seq:06d}"`
  - 因此：第一个 block 为 `cb_000001`，第二个为 `cb_000002`，以此类推
- **关联规则**：
  - `ToolResultBlock.tool_call_id` 必填
  - `ToolResultBlock.tool_use_id` 必填（=对应 `ToolUseBlock.id`），不能只靠相邻位置，需支持乱序返回。
- **delta vs snapshot**：
  - `thinking/text`：delta 追加到“当前开放 block”的 `text`
  - `tool_use.arguments_text`：流式分片追加；仅在 round 结束时解析出 `arguments_json = json.loads(arguments_text)`（解析失败需容错）

## 流式输出协议（SSE）

- **统一事件**：新增 `content_block`（迁移完成后不再使用 `mcp_tool_call` / `reasoning` / `content`）。
- **统一 payload（操作语义）**：
  - `op: "append"` + `{ block }`：新增一个 block（顺序即时间线顺序）
  - `op: "delta"` + `{ block_id, delta }`：对 text/thinking 的增量追加
  - `op: "tool_delta"` + `{ block_id, tool_call_id?, name?, arguments_delta }`：对 tool_use 的增量追加
    - `tool_call_id` 未出现前：后端先 `append` 一个 `ToolUseBlock`（带稳定的 `ToolUseBlock.id`）
    - 后端内部仍可用 `tool_index` 聚合 OpenAI 流式分片，但不透传给前端；前端仅按 `block_id` 合并 `arguments_delta`
    - 当 `tool_call_id` 出现后：补齐 `ToolUseBlock.tool_call_id`，并建立 `tool_call_id -> tool_use_block_id` 关联供 tool_result 回指
  - `op: "finalize_round"`：本轮 tool_calls 已定型（前端可在此时解析 `arguments_json` 并补齐字段）
  - `op: "done"`：整次消息完成

## 后端改造点

- **Schema / API**：
  - 在 `[backend/app/schemas/chat.py](backend/app/schemas/chat.py)` 新增 `ContentBlock`/子类型与 `ChatMessageItem.content_blocks`
  - 更新 `ChatRequest`：由 `content: str` 改为 `content_blocks: list[ContentBlock]`
  - 联动更新 `[backend/app/api/chat.py](backend/app/api/chat.py)`、`[backend/app/services/chat/chat_service.py](backend/app/services/chat/chat_service.py)` 的取值方式（统一从 blocks 提取用户文本）
- **Agent 聚合器（流式输出与聚合）**：
  - 在 `[backend/app/agents/chat_session_agent.py](backend/app/agents/chat_session_agent.py)` 引入 `ContentBlocksAggregator`（建议放 `backend/app/agents/utils/`）
  - 职责：
    - 维护 `content_blocks` 数组与“当前开放 text/thinking block id”
    - tool_calls 分片：以 `delta.tool_calls[i].index` 作为内部稳定 key，对应一个 `ToolUseBlock`，持续追加其 `arguments_text`；收到 `tc.id` 时写入 `tool_call_id`
    - 执行工具后：产出 `ToolResultBlock`，用 `tool_call_id` + `tool_use_id` 精确关联
    - 每次变更都产出对应 `content_block` SSE（`append/delta/tool_delta/finalize_round/done`）
- **落库 / 迁移**：
  - 在 `[backend/app/models/message_db.py](backend/app/models/message_db.py)` 的 `MessageDb` 新增 `content_blocks: list[dict[str, Any]] | None`（SQL JSON）
  - 更新 `[backend/app/services/message/message_db.py](backend/app/services/message/message_db.py)`：
    - 用户消息写入 `content_blocks`
    - `update_assistant_message` 写入 assistant 侧 `content_blocks`
    - 兼容期：由 blocks 派生旧字段 `content`（拼接 text）与 `reasoning`（拼接 thinking），避免搜索/展示链路立刻断裂
  - 新增 Alembic 迁移：为 `messages` 表增加 `content_blocks` JSON 列（默认 NULL）
- **历史消息处理链路（必须改造）**：
  - 当前历史窗口与“喂给 LLM 的 history”由 `[backend/app/services/chat/chat_service.py](backend/app/services/chat/chat_service.py)` 负责：
    - `prepare_history_messages(...)`：先 `truncate_history_by_rounds_and_tokens(...)`（轮+token 截断），再 `process_history_messages(...)`（把 `tool_calls` 扁平化并对“非最新工具轮”做 summary/截断）
  - 引入 `content_blocks` 后需要：
    - **token 计数对齐 blocks**：`truncate_history_by_rounds_and_tokens` 改为对 blocks 做“可计 token 的派生视图”，保持“按整轮（user+assistant）”截断语义不变
    - **工具轮扁平化对齐 blocks**：`process_history_messages` 从 blocks 抽取 `ToolUseBlock/ToolResultBlock` 来生成喂给 LLM 的 tool-call messages，并复用现有“非最新轮：summary 优先，否则按 token 截断”的策略
    - **窗口外摘要对齐 blocks**：`ContextSummaryService.summarize_merge(...)` 输入使用从 blocks 派生的“可摘要文本”，避免超长工具输出污染摘要
    - **统一提取用户文本**：`ChatService.stream_response/stream_message`、`ChatSessionAgent` 等处不再直接读 `chat_request.content`，统一走 `extract_user_text(chat_request.content_blocks)`（标题生成、记忆检索、Mem0 写入、工具提示 user message 组装等）
    - 迁移不考虑兼容期回填：假设历史/DB 均已有 `content_blocks`

## 前端改造点

- **类型（接口层）**：
  - 在 `frontend/src/interfaces/` 新增 `ContentBlock` 联合类型（`TextBlock/ThinkingBlock/ToolUseBlock/ToolResultBlock`），并在 `frontend/src/interfaces/index.ts` 导出
  - 在 `frontend/src/interfaces/chat.ts` 的 `ChatMessage` 增加 `contentBlocks: ContentBlock[]`
  - 不保留旧字段：移除 `content/reasoning/toolCalls`，渲染与流式合并仅使用 `contentBlocks`
  - `frontend/src/interfaces/tooCall.ts` 属于旧 `mcp_tool_call` timeline：迁移完成后应移除对应渲染与类型依赖
- **流式协议接入（SSE types）**：
  - 在 `frontend/src/interfaces/apiRequest.ts` 为 `StreamMessage` 新增 `type: "content_block"` 分支，`data` 对齐后端 `{ op, ... }`
  - 不保留旧分支：移除 `reasoning/content/mcp_tool_call` 分支，仅保留 `ack/refresh_conversation/title/content_block/done/error`
- **流式合并（hook 层）**：
  - 在 `frontend/src/hooks/chat.ts` 的 `messageHandlers: StreamMessageHandlerMap` 新增 `content_block` handler，按 `op` 分发到 Store reducers
  - 当 `content_block` 可用后，停止触发旧的 `appendReasoningToLastMessage/appendContentToLastMessage/appendMcpToolCallToLastMessage`
  - 下线 `createToolCallHandler(...)` 及其 `EventType.McpToolCallDone/EventType.ReasoningDone` 依赖（折叠/完成信号改由 `finalize_round/done` 或 block 状态驱动）
- **Store（Redux slice）**：
  - 在 `frontend/src/store/slices/chatSlice.ts` 新增 reducers（都带 `conversationId`，只操作最后一条 assistant 消息）：
    - `appendBlockToLastMessage`（`op: "append"`）
    - `appendDeltaToBlock`（`op: "delta"`）
    - `appendToolUseArgumentsDelta`（`op: "tool_delta"`）
    - `finalizeToolUseArgumentsJson`（`op: "finalize_round"`）
    - `appendToolResultBlock`（通常走 `op: "append"`，也可单独 op）
  - 迁移完成后删除旧 reducers：
    - `appendMcpToolCallToLastMessage`
    - `appendReasoningToLastMessage`
    - `appendContentToLastMessage`
- **渲染（ChatMessage 组件树）**：
  - 在 `frontend/src/pages/ChatPage/components/ChatMessage/components/AssistantMessage.tsx`：
    - 由 “ToolCallBlock → ReasoningBlock → Markdown(message.content)” 改为按 `message.contentBlocks` 顺序统一渲染（例如新增 `ContentBlocksRenderer`）
    - 不考虑兼容：仅按 `contentBlocks` 渲染，不再回退旧渲染

## 迁移与验证

- **DB**：
  - 跑迁移后，本地发起一次包含并行 tool_calls 的对话，验证 `messages.content_blocks` 能完整重放时间线
- **SSE**：
  - `tool_use` block 数量与最终 tool_calls 数一致
  - tool_result 在并行/乱序下仍可通过 `tool_call_id` 精确回指对应 tool_use（且 `tool_use_id` 正确）
- **UI**：
  - 前端能 token/片段级展示 thinking/text
  - 工具调用与结果按 block 顺序展示，且乱序结果不串位
