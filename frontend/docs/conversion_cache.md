## 对话缓存

### 缓存数据结构

```js
{
  "{conversationId}": {
    messages: [] as ChatMessage[],
    messageLoaded: boolean,
    lastMessageUpdateAt: string, // 等价于 messages.at(-1).updatedAt
    isLoading: boolean,
    isStreaming: boolean,
    isReasoning: boolean,
    isCallingTools: boolean,
  }
}
```


### ChatPage 缓存策略

1. 首先，页面加载时，会拉取最新的 conversion_info 数据，并缓存到 indexedDB 中
2. 然后，用户切换至某个对话时，
  2.1 如果 messageLoaded 为 false，则拉取完整消息列表
  2.2 否则，携带对话的 conversion_id 和 last_message_updated_at 时间戳，到服务器查询是否需要更新缓存
    2.2.1 如果 response.status=304，则直接使用缓存中的数据
    2.2.2 否则，拉取最新的 messages 数据，并缓存到 indexedDB 中

对话 last_message_updated_at 时间戳更新时机如下:
- 最后一条消息的 created_at 时间戳
