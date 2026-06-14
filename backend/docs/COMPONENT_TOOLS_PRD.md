# 组件工具接入说明（历史归档）

> 状态：历史文档。本文保留旧版组件工具方案的背景，不再作为当前实现依据。
> 当前 `ChatRequest` 已无 `component_tools_for_backend` 字段，后端也不再包含 `ComponentToolsAgent` 与 `app/services/component/` 链路。

## 当前实现口径

现网聊天链路以 `POST /api/chat/stream` 为入口：

1. `ChatService` 组装 `ChatOrchestrator` 所需依赖。
2. `ChatOrchestrator.run_chat_turn` 处理历史上下文、用户记忆、附件 KB 上下文与消息持久化。
3. `ChatSessionAgent.stream_session_events` 在同一个会话消息线程中完成 MCP 工具多轮调用与最终回答。
4. SSE 以 `content_block` / `content_block_done` / `done` 等事件向前端推送结构化内容。

相关源码：

- `app/schemas/chat.py`：当前 `ChatRequest` 字段定义。
- `app/services/chat/chat_service.py`：聊天服务门面。
- `app/services/chat/chat_orchestrator.py`：单轮聊天生命周期编排。
- `app/agents/chat_session_agent.py`：MCP 工具调用与最终应答的单会话 Agent。

## 已下线的旧口径

以下概念属于历史方案，不应在新代码或新文档中继续使用：

- `component_tools_for_backend`
- `ComponentToolConfig` / `ComponentToolWhen`
- `ComponentToolsAgent`
- `component_tool_calls` / `component_tool_calls_duration`
- `app/services/component/`
- `app/agents/component_tools_agent.py`

如需了解当前工具调用、工具命名与 MCP 配置，请阅读：

- `backend/docs/MCP_CONFIG_ANALYSIS.md`
- `backend/docs/RETRIEVAL_SYSTEM.md`
- `frontend/docs/schema-for-backend-usage.md`
