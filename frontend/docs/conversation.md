# AI 助手会话交互说明（当前实现）

本文档描述前端会话相关的路由、状态与接口对接，按当前 `frontend/src` 与后端 `/api/conversation/*`、`/api/chat/stream` 实现整理。

## 1. 路由

当前前端路由：

- `/`：重定向到 `/chat`
- `/chat`：欢迎页（空聊天页）
- `/chat/:conversationId`：具体会话页
- `/login`、`/login/wechat/callback`：登录相关页面
- `/markdown`：Markdown 示例页

## 2. 会话接口映射

前端在 `src/services/conversation.ts` 中统一调用以下接口（通过 `apiClient`，最终前缀为 `/api`）：

- 创建会话：`POST /api/conversation/register`
- 会话列表：`GET /api/conversation/list`
- 会话详情：`GET /api/conversation/detail/{conversationId}`
- 更新会话：`PUT /api/conversation/update/{conversationId}`
- 删除会话：`DELETE /api/conversation/delete/{conversationId}`

消息与流式接口在 `src/services/chat.ts`：

- 会话消息：`GET /api/conversation/{conversationId}/messages`
- 删除消息：`DELETE /api/message/delete/{messageId}`
- 流式聊天：`POST /api/chat/stream`（SSE）

## 3. SSE 协议与前端处理

### 3.1 后端消息格式

后端使用 `data:` 行返回 JSON（不使用 `event:` 行）：

```text
data: {"type":"ack","data":{...}}
```

前端在 `src/services/chat.ts` 中对 `event.data` 做两步处理：

1. `JSON.parse(event.data)`
2. `camelcaseKeys(..., { deep: true })`

因此后端蛇形字段（例如 `updated_at`）会变为前端驼峰字段（`updatedAt`）。

### 3.2 事件类型（按典型时序）

`src/hooks/chat.ts` 中注册的事件处理器如下：

1. `ack`
2. `refresh_conversation`
3. `title`（可选）
4. `mcp_tool_call`（0~N 条，最后可能出现 `{ status: "done" }`）
5. `reasoning`（`status: start | continue | done`）
6. `content`（`status: start | continue | done`）
7. `done`
8. `error`

> 注意：现网工具事件名是 `mcp_tool_call`，不是 `tool_call`。

### 3.3 关键约束与坑点

- 前端通过 `type` 分发消息，不依赖 SSE `event` 字段。
- `reasoning/content` 都是分段流，`status=done` 代表该阶段结束，不代表整次请求结束。
- `done` 才表示本次消息流完成，随后前端会更新消息状态并重置流状态。
- 后端 `done.data` 当前返回 `updated_at`；经 `camelcaseKeys` 后为 `updatedAt`。前端若读取 `lastMessageUpdatedAt`，需做兼容处理。

## 4. 典型交互流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端
    participant API as 后端

    U->>FE: 进入 /chat
    U->>FE: 点击新建对话
    FE->>API: POST /api/conversation/register
    API-->>FE: 返回 conversation id
    FE->>FE: 跳转 /chat/{conversationId}

    U->>FE: 发送消息
    FE->>API: POST /api/chat/stream
    API-->>FE: SSE ack + refresh_conversation + mcp_tool_call/reasoning/content + done

    U->>FE: 打开历史会话
    FE->>API: GET /api/conversation/{conversationId}/messages
    API-->>FE: 返回消息列表
```

## 5. 鉴权与错误处理

- 受保护接口请求需带 `Authorization: Bearer <token>`；
- token 由登录接口响应头 `x-secret-token-info` 下发并在前端存储；
- 当接口返回 `401`（包括 SSE `onopen` 阶段），前端清理鉴权信息并跳转登录页。

## 6. 与旧文档差异

- 当前实现不使用 `/conversations` 风格路径，统一为 `/api/conversation/*`；
- 当前文档不再将 ChromaDB、Redis 作为前端会话能力依赖；
- 当前推荐的开发命令统一使用 `vp`（例如 `vp dev`、`vp build`）。
