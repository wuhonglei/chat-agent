# 前端请求体给后端使用说明（当前实现）

## 1. 结论

当前聊天请求不包含组件工具 schema，也不包含 `componentToolsForBackend`。

前端发送给 `POST /api/chat/stream` 的核心字段来自 `ChatRequest`（`src/interfaces/chat.ts`）：

- `contentBlocks`
- `conversationId`
- `historyIds`
- `removedMessageIds`
- `regenerateTitle`
- `thinkMode`
- `agentMode`（0=关闭，1=开启）
- `modelID`
- `clientTurnId`
- `mentionedBlocks`（可选，@ 引用附件）
- `taskAction`（可选，`"continue"` | `"summarize"`；Agent 检查点后续跑 / 总结）

请求发出前会在 `src/services/chat.ts` 中通过 `snakecaseKeys` 转为后端蛇形字段，例如：

- `contentBlocks` -> `content_blocks`
- `conversationId` -> `conversation_id`
- `historyIds` -> `history_ids`
- `removedMessageIds` -> `removed_message_ids`
- `modelID` -> `model_id`
- `agentMode` -> `agent_mode`
- `clientTurnId` -> `client_turn_id`
- `taskAction` -> `task_action`

后端另支持可选 `memories`（预注入用户记忆、跳过服务端 search）；**前端现网不发送**，仅评估 / replay 等脚本使用。`task_action` 为 `continue` / `summarize` 时后端也会跳过记忆检索。详见 `backend/docs/用户管理.md`、`docs/会话管理.md`。

## 2. 为什么这里不再记录组件 schema 传输

仓库当前代码中：

- 前端 `src/interfaces/chat.ts` 的 `ChatRequest` 无 `componentToolsForBackend`
- 后端 `backend/app/schemas/chat.py` 的 `ChatRequest` 无 `component_tools_for_backend`

因此“前端随请求传组件规则/Schema，后端按该字段消费”的口径不适用于现网实现。

## 3. 可直接复用的请求示例

```json
{
  "contentBlocks": [
    {
      "id": "cb_user_text_1",
      "type": "text",
      "text": "帮我总结今天的 AI 新闻"
    }
  ],
  "conversationId": "c123",
  "historyIds": ["m1", "m2"],
  "removedMessageIds": [],
  "regenerateTitle": false,
  "thinkMode": true,
  "agentMode": 1,
  "modelID": "default",
  "clientTurnId": "turn_...",
  "taskAction": "continue"
}
```

> 实际发送到后端时会自动转换为 snake_case。

## 4. 常见坑

- 直接按旧文档添加 `componentToolsForBackend`，后端不会消费该字段。
- 调试抓包时看到后端字段名与前端 TS 类型不一致是正常现象（snake_case 转换导致）。
- `taskAction` 仅 `agentMode > 0` 时生效；普通模式即使带上也会被忽略，工具预算仍是 10 轮。
- 检查点续跑/总结应带固定按钮文案；不要把 `taskAction` 用在用户新输入的普通一轮上（后端会跳过记忆检索）。
