## 对话缓存

### 缓存数据结构

```json
{
  "{conversationId}": {
    messages: [] as ChatMessage[],
    isLoading: false,
    isStreaming: false,
    isReasoning: false,
    isCallingTools: false,
  }
}
```


### ChatPage 缓存策略

1. 首先，页面加载时，会拉取最新的 conversion_info 数据，并缓存到 indexedDB 中
2. 然后，用户切换至某个对话时，携带对话的 conversion_id 和 last_message_created_at 时间戳，到服务器查询是否需要更新缓存
3. 如果需要更新缓存，则拉取最新的 messages 数据，并缓存到 indexedDB 中
4. 如果不需要更新缓存，则直接使用缓存中的数据

对话 last_message_created_at 时间戳更新时机如下:
- 最后一条消息的 created_at 时间戳
