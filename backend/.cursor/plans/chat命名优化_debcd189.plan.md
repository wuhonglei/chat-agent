---
name: chat命名优化
overview: 梳理 AI 回复主链路中的函数名和变量名，先统一主链路语义，再逐步清理 Agent 与上下文处理层的高频歧义命名，最后视影响面决定是否推进 schema 术语统一。
todos:
  - id: rename-main-flow
    content: 重命名 API、ChatService、ChatOrchestrator 的主链路函数，明确 stream/run/collect 分层语义
    status: completed
  - id: rename-orchestrator-vars
    content: 统一 ChatService 与 ChatOrchestrator 的高频变量名，消除 response/message/payload/chunk 混用
    status: completed
  - id: rename-agent-flow
    content: 收敛 ChatSessionAgent 与状态机命名，统一 round/session/event/prompt 术语
    status: completed
  - id: rename-tool-policy
    content: 统一 MCP 工具会话与策略层命名，减少 ctx/args/state 等泛化名称
    status: completed
  - id: evaluate-schema-names
    content: 评估是否推进 schema 层高影响面重命名，并与内部命名优化拆分实施
    status: completed
isProject: false
---

# AI 回复流程命名优化计划

## 目标
- 提升 AI 回复主链路的可读性，让“入口、编排、轮次执行、收尾落库”在命名上清晰分层。
- 减少 `stream/response/message/execute/payload` 等同义词混用带来的理解成本。
- 采用低风险分批重命名方式，优先修改调用链清晰、收益高、影响小的标识符。

## 范围
- 入口与编排层：[`app/api/chat.py`](`app/api/chat.py`)、[`app/services/chat/chat_service.py`](`app/services/chat/chat_service.py`)、[`app/services/chat/chat_orchestrator.py`](`app/services/chat/chat_orchestrator.py`)
- Agent 执行层：[`app/agents/chat_session_agent.py`](`app/agents/chat_session_agent.py`)、[`app/agents/chat_session_state.py`](`app/agents/chat_session_state.py`)、[`app/agents/mcp_tool_execution.py`](`app/agents/mcp_tool_execution.py`)、[`app/agents/tool_call_policy.py`](`app/agents/tool_call_policy.py`)
- 上下文与收尾层：[`app/services/chat/history_context_service.py`](`app/services/chat/history_context_service.py`)、[`app/services/chat/post_process_service.py`](`app/services/chat/post_process_service.py`)
- 视影响面决定是否扩展到 schema：[`app/schemas/chat.py`](`app/schemas/chat.py`)

## 命名原则
- `stream_*`：仅用于真正输出 SSE 事件流的函数。
- `run_*`：用于 orchestrator 级别的完整流程入口。
- `prepare_*`：仅用于上下文准备与预处理。
- `collect_*`：用于从运行态聚合最终结果。
- `persist_*`：仅用于同步落库。
- `schedule_*`：仅用于异步后台任务调度。
- 术语统一：
  - `event` 表示 SSE 单元
  - `message` 表示领域消息 / LLM message / DB message
  - `response` 表示最终助手聚合结果
  - `round` 表示一轮模型输出与工具调用
  - `turn` 表示一次完整用户输入到助手完成的流程

## 分阶段实施

### 阶段 1：主链路函数重命名
- 在 [`app/api/chat.py`](`app/api/chat.py`) 中，将 `chat_stream` 调整为 `stream_chat`。
- 在 [`app/services/chat/chat_service.py`](`app/services/chat/chat_service.py`) 中，将 `stream_response` 调整为 `stream_chat_events`。
- 在 [`app/services/chat/chat_orchestrator.py`](`app/services/chat/chat_orchestrator.py`) 中：
  - `stream_response` -> `run_chat_turn`
  - `stream_message` -> `stream_turn_events`
  - `generate_title` -> `generate_title_event`
  - `get_collected_response` -> `collect_assistant_response`
- 同步所有调用点，确保 API 入口到 orchestrator 的调用链在命名上变为“stream -> run -> stream -> collect/persist”。

### 阶段 2：编排层变量语义统一
- 在 [`app/api/chat.py`](`app/api/chat.py`) 中：
  - `messages_result` -> `created_messages`
- 在 [`app/services/chat/chat_service.py`](`app/services/chat/chat_service.py`) 中：
  - `_search_memories` -> `_search_user_memories`
  - `orchestrator` 字段 -> `chat_orchestrator`
  - SSE 迭代变量 `chunk` -> `event`
- 在 [`app/services/chat/chat_orchestrator.py`](`app/services/chat/chat_orchestrator.py`) 中：
  - `raw_history` -> `history_messages_from_db`
  - `new_history_messages` -> `prepared_history_messages`
  - `window_out_summary` -> `history_summary_before_window`
  - `user_memory_texts` -> `user_memories`
  - `assistant_payload` -> `assistant_response`
  - `done_payload` -> `done_event_payload`
  - `title_message` -> `title_event`
  - `chunk` / `chunk_count` -> `event` / `event_count`

### 阶段 3：Agent 层命名收敛
- 在 [`app/agents/chat_session_agent.py`](`app/agents/chat_session_agent.py`) 中：
  - `stream_execute` -> `stream_session_events`
  - `aggregate` -> `session_output`
  - `blocks_aggregator` -> `content_block_aggregator`
  - `output_messages` -> `tool_round_messages`
  - `_sync_collected_content` -> `_sync_session_output`
  - `_build_round_messages` -> `_build_round_prompt_messages`
  - `_check_tool_context_budget` -> `_check_round_context_budget`
  - `_stream_final_answer_round` -> `_stream_final_round_events`
  - `_stream_one_round_with_tools` -> `_stream_tool_round_events`
- 同时清理核心局部变量：
  - `messages` -> `base_prompt_messages`
  - `llm_messages` -> `round_prompt_messages`
  - `tool_ctx` -> `tool_session`
  - `tool_acc` -> `tool_call_deltas_by_index`
  - `full_reasoning` -> `accumulated_reasoning`
  - `full_content` -> `accumulated_content`
  - `choice0` -> `first_choice`
  - `rc` -> `reasoning_delta`
  - `ct` -> `content_delta`
  - `assistant_message` -> `assistant_tool_use_message`
  - `tool_results` -> `tool_result_messages`

### 阶段 4：状态机与工具策略命名统一
- 在 [`app/agents/chat_session_state.py`](`app/agents/chat_session_state.py`) 中：
  - `SessionAggregate` -> `SessionOutput`
  - `RoundExecution` -> `RoundState`
  - `current` -> `current_round`
  - `final_answer_done` -> `is_final_answer_complete`
- 在 [`app/agents/mcp_tool_execution.py`](`app/agents/mcp_tool_execution.py`) 中：
  - `get_mcp_server_names` -> `resolve_enabled_mcp_servers`
  - `get_tools_state` -> `get_available_tools`
  - `should_continue_tool_calls` -> `should_continue_rounds`
  - `tool_call_user_message` -> `tool_guided_user_message`
- 在 [`app/agents/tool_call_policy.py`](`app/agents/tool_call_policy.py`) 中：
  - `tool_call_args_by_name` -> `tool_arguments_history_by_name`
  - `suffix_user_message` -> `hint_messages`
  - `continue_message` -> `stop_reason_message`
  - `_extract_tool_call_arguments` -> `_group_tool_call_arguments_by_name`
  - `tool_arguments` -> `tool_arguments_by_name`

### 阶段 5：上下文与 schema 术语评估
- 在 [`app/services/chat/history_context_service.py`](`app/services/chat/history_context_service.py`) 中，评估并清理上下文准备相关变量名：
  - `process_history_messages` -> `compress_history_messages`
  - `compressed_in_window` -> `compressed_window_messages`
  - `final_in_window` -> `window_messages_after_truncation`
  - `before_window_summary` -> `stored_summary_before_window`
- 在 [`app/services/chat/post_process_service.py`](`app/services/chat/post_process_service.py`) 中：
  - `persist_assistant_response` -> `persist_final_assistant_message`
  - `schedule_memory_persist` -> `schedule_memory_write`
  - `update_service` -> `message_service`
  - `conv` -> `conversation`
  - `asst_msg` -> `assistant_message`
- 最后评估 [`app/schemas/chat.py`](`app/schemas/chat.py`) 中是否需要推进高影响面重命名：
  - `CollectedResponse` -> `AssistantResponse`
  - `ChatMessageItemReq` -> `ChatMessageRequestItem`
  - `ChatMessageItem` -> `ChatMessage`
- 这一阶段应单独判断影响面，避免把“代码语义改善”升级成“大范围接口名迁移”。

## 验证方式
- 静态验证：全局检查重命名后的引用是否完整，没有残留旧标识符。
- 可读性验证：主链路从 API 到 Agent 能否一眼看出 `stream_chat -> stream_chat_events -> run_chat_turn -> stream_turn_events -> stream_session_events` 的层级关系。
- 回归验证：确认重命名不改变函数输入输出与行为，尤其是 SSE 事件构造、消息落库、标题生成与记忆写入流程。

## 风险与控制
- 风险最高的是 schema 与跨层模型名调整，因为影响范围大，可能牵涉序列化与更多调用方。
- 前四个阶段尽量限制在“内部命名优化”，不改变 API 结构、不修改业务语义。
- 每一阶段完成后都应单独检查调用链，避免一次性大改导致引用遗漏。
