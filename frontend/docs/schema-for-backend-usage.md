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
- `modelID`

请求发出前会在 `src/services/chat.ts` 中通过 `snakecaseKeys` 转为后端蛇形字段，例如：

- `contentBlocks` -> `content_blocks`
- `conversationId` -> `conversation_id`
- `historyIds` -> `history_ids`
- `removedMessageIds` -> `removed_message_ids`
- `modelID` -> `model_id`

`modelID` 的值使用后端 `GET /api/chat/models` 返回的 `model_id`，格式为
`provider/model_name`。若前端传空字符串或后端无法解析该引用，聊天接口会回退到
`text_generation.default_model`。

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
  "modelID": "dashscope/kimi-k2.6"
}
```

> 实际发送到后端时会自动转换为 snake_case。

## 4. 模型列表加载与缓存

前端模型选择来自 `GET /api/chat/models`。Redux `modelsSlice` 会用
`localStorage["chat-models-cache-v1"]` 缓存上一次的模型列表，用于刷新页面后立即显示历史已选模型名称。

约束：

- 缓存只用于首屏 hydrate，`loaded` 初始仍为 `false`，接口返回后会覆盖缓存；
- 接口加载完成后，若当前 `modelID` 为空或不在返回列表中，前端使用 `models[0].modelId` 作为默认值；
- 隐私模式、配额超限或 JSON 解析失败时会静默降级为空缓存。

## 5. 常见坑

- 直接按旧文档添加 `componentToolsForBackend`，后端不会消费该字段。
- 调试抓包时看到后端字段名与前端 TS 类型不一致是正常现象（snake_case 转换导致）。
- 不要再使用旧的 `"default"` 作为模型 ID；需要传后端返回的 `provider/model_name`，或传空值让后端回退默认模型。
