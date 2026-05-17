# 检索系统说明（当前实现与规划边界）

> 状态：本文件用于澄清“当前已落地能力”和“规划能力”。
> 结论：当前主流程走 `POST /api/chat/stream` + MCP 工具调用；独立 `/api/retrieval/*` 接口未在主应用注册。

## 1. 当前实现（现网）

### 1.1 入口与调用链路

- 对话入口：`POST /api/chat/stream`
- 核心服务：`app/services/chat/chat_service.py`
- MCP 管理：`app/mcp/mcp_client.py`

简化链路：

1. 前端请求 `POST /api/chat/stream`
2. 后端写入用户/助手占位消息并返回 SSE `ack`
3. `ChatService` 调用 `MCPToolsAgent`，由 `MCPClientManager` 按工具路由到 MCP Server
4. 模型结合工具结果继续生成内容
5. 回写助手消息并输出 SSE `done`

### 1.2 当前可用 MCP 服务

当前 `mcp_client.py` 注册并参与工具编排的服务：

- `context7-mcp`
- `weather-mcp`
- `tavily-mcp`
- `code-exec-mcp`
- `time-mcp`

### 1.3 与“检索”相关的现网能力

- 联网检索由 `tavily-mcp` 提供
- 文档/API 知识检索由 `context7-mcp` 提供
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
    "content": "帮我检索最新的 AI Agent 工程实践",
    "conversation_id": "your-conversation-id",
    "history_ids": [],
    "think_mode": false,
    "component_tools_for_backend": []
  }'
```

说明：

- 该请求会由后端按需调用 MCP 工具（如 tavily/context7），并通过 SSE 持续返回结果；
- 消息持久化与标题事件同样在该链路内处理。

## 4. 技术栈口径（按当前实现）

- Web/API：FastAPI
- 对话编排：Agent 架构 + MCP 工具路由
- 数据库：PostgreSQL（含 pgvector 扩展能力）
- MCP：fastmcp
