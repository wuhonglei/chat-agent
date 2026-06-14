# 检索与 MCP 工具链路说明（当前实现与规划边界）

> 状态：本文件用于澄清“当前已落地能力”和“规划能力”。
> 结论：当前主流程走 `POST /api/chat/stream` + `ChatSessionAgent` 内的 MCP 工具调用；独立 `/api/retrieval/*` 接口未在主应用注册。

## 1. 当前实现（现网）

### 1.1 入口与调用链路

- 对话入口：`POST /api/chat/stream`
- 核心服务：`app/services/chat/chat_service.py`
- 编排服务：`app/services/chat/chat_orchestrator.py`
- 会话 Agent：`app/agents/chat_session_agent.py`
- MCP 管理：`app/mcp/client.py`

简化链路：

1. 前端请求 `POST /api/chat/stream`
2. 后端写入用户/助手占位消息并返回 SSE `ack`
3. `ChatService` 组装 `ChatSessionAgent`、`TitleGenerationAgent`、历史上下文、KB RAG 与用户记忆服务
4. `ChatOrchestrator.run_chat_turn` 读取历史消息、用户记忆和附件 KB 上下文，然后调用 `ChatSessionAgent.stream_session_events`
5. `ChatSessionAgent` 根据 `agent_mode` 选择 MCP Server 列表，执行多轮工具调用或直接生成最终回复
6. `PostProcessService` 回写助手消息，最后输出 SSE `done`

### 1.2 当前可用 MCP 服务

当前由 `MCPRegistry` + `MCPClientManager` 注册并参与工具编排的服务（配置键）：

- `context7`
- `weather`
- `tavily`
- `time`
- `code`
- `file`
- `skill_manager`
- `shell`

LLM 可见工具名为 `{server}_{bare}`，例如 `tavily_web_search`；MCP 协议层仍为 `web_search`（见 `app/mcp/tool_naming.py`）。

服务注册与请求期暴露是两层控制：

- `settings.mcp.mcp_servers` 控制 Server 如何注册，支持 `fastmcp`、`http`、`stdio` 三种传输方式，并可用 `enabled: false` 禁用单个 Server。
- `settings.mcp.normal_mode_servers` 控制普通对话（`agent_mode=0`）暴露给 LLM 的工具集合。
- `settings.mcp.agent_mode_servers` 控制 Agent 模式（`agent_mode>0`）暴露给 LLM 的工具集合，默认包含文件、技能管理和 Shell 相关能力。

### 1.3 与「检索」相关的现网能力

- 联网检索由 `tavily` 提供（LLM 工具名如 `tavily_web_search`）
- 文档/API 知识检索由 `context7` 提供
- 会话附件 KB 上下文由 `KbRagContextService` 构造为服务端 `kb_context` 内容块，并注入当前轮提示词
- 统一通过聊天流接口触发，不暴露独立检索 REST 端点

## 2. 当前未落地（仅规划）

以下能力在文档中可能出现，但不属于当前主应用可调用接口：

- `POST /api/retrieval/search`
- `GET /api/retrieval/health`
- `GET /api/retrieval/sources`
- `POST /api/chat`（非流式版本）

如需实现上述接口，应在 `app/main.py` 注册对应路由并补齐服务层与鉴权策略。

## 3. 推荐调用示例（当前可用）

```bash
curl -N -X POST "http://localhost:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{
    "content_blocks": [
      {
        "id": "cb_user_text_1",
        "type": "text",
        "text": "帮我检索最新的 AI Agent 工程实践"
      }
    ],
    "conversation_id": "your-conversation-id",
    "history_ids": [],
    "removed_message_ids": [],
    "regenerate_title": false,
    "agent_mode": 0,
    "think_mode": false,
    "model_id": "dashscope/kimi-k2.6",
    "client_turn_id": "client-turn-uuid"
  }'
```

说明：

- 该请求会由后端按需调用 MCP 工具（如 tavily/context7），并通过 SSE 持续返回结果；
- `agent_mode=0` 使用普通工具集合；`agent_mode>0` 使用 Agent 模式工具集合；
- `kb_context` 是服务端生成的内容块，客户端请求体不能直接提交该类型；
- 消息持久化、标题事件、停止状态与最终 `done` 事件同样在该链路内处理。

## 4. 技术栈口径（按当前实现）

- Web/API：FastAPI
- 对话编排：`ChatOrchestrator` + `ChatSessionAgent` + MCP 工具路由
- 数据库：PostgreSQL（含 pgvector 扩展能力）
- MCP：fastmcp
