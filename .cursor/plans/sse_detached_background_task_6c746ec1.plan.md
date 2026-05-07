---
name: SSE detached background task
overview: 在 /chat/stream 接口层把 SSE 事件的"生产"与"消费"解耦：用后台 asyncio.Task 跑业务逻辑、用 asyncio.Queue 桥接 SSE 输出。客户端断开仅取消 HTTP 消费协程，后台生产任务继续完成助手消息持久化与 Mem0 记忆写入。
todos:
  - id: add-helpers
    content: 在 backend/app/api/chat.py 中新增模块级 _BACKGROUND_TASKS、_run_producer、_drain_queue、_run_detached_sse_stream 辅助实现
    status: completed
  - id: rewire-endpoint
    content: 重接 stream_chat：用 _run_detached_sse_stream 包装 chat_service.stream_chat_events 后交给 StreamingResponse
    status: completed
  - id: logs
    content: 补充“消费者断开”与“后台任务完成”的 INFO 日志（含 conversation_id/assistant_message_id）
    status: completed
  - id: manual-verify
    content: 本地验证：问答中途关闭浏览器，确认无 CancelledError 堆栈且助手消息完整落库
    status: completed
isProject: false
---

## 背景

当前 [backend/app/api/chat.py:58-66](backend/app/api/chat.py) 直接把 `chat_service.stream_chat_events(...)` 这个异步生成器交给 `StreamingResponse`。浏览器断开时 Starlette 会取消该生成器，`CancelledError` 注入后会跳过 [chat_orchestrator.py](backend/app/services/chat/chat_orchestrator.py) 中位于事件流之后的：

- `persist_final_assistant_message`（落库助手消息）
- `schedule_memory_write`（写入 Mem0 记忆）
- `build_done_event`（结束事件）

且 `except Exception` 不会捕获 `CancelledError`，导致日志里出现裸的取消异常堆栈。

## 设计

引入"生产/消费解耦"的最小化改造，仅作用于 `chat.py` 接口本身：

```mermaid
flowchart LR
    Client[浏览器] -.SSE.-> Resp[StreamingResponse]
    Resp --> Consumer[消费协程 _drain_queue]
    Consumer --> Q[(asyncio.Queue)]
    Q <-- put --- Producer[后台 Task _run_producer]
    Producer --> Service[chat_service.stream_chat_events]
    Service --> Persist[持久化 + 记忆写入 + done 事件]
    Client -.断开.-> Consumer
    Consumer -.cancel 仅消费侧.-> X[(队列被丢弃)]
    Producer -.不受影响.-> Persist
```

- 客户端断开 → 只有消费协程被取消 → 后台生产任务继续跑完业务，正常落库与写记忆。
- 用模块级 `set` 持有任务引用，避免被 GC（fire-and-forget，关闭时不特殊处理）。

## 改动点

### 1. 改造 [backend/app/api/chat.py](backend/app/api/chat.py)

将原来的：

```python
return StreamingResponse(
    chat_service.stream_chat_events(
        chat_request,
        created_messages.user_message_id,
        created_messages.assistant_message_id,
        user_id=auth_info.user_id,
    ),
    media_type="text/event-stream",
)
```

替换为通过本地辅助函数 `_run_detached_sse_stream(...)` 包裹后再交给 `StreamingResponse`。新增（同文件内）以下要点：

- **模块级集合**：`_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()` 用来持有后台任务，防止被 GC。
- **`_run_producer(agen, queue, sentinel, log_ctx)`**：异步函数，逐个把 `agen` 的事件 `put` 到 `queue`；正常结束/异常结束/`CancelledError`（理论上不会触发，但兜底）都会在 `finally` 里 `put(sentinel)` 终止消费侧。异常时记录 `logger.error` 并向队列发送一个 `build_error_event`。
- **`_drain_queue(queue, sentinel)`**：异步生成器，循环 `await queue.get()`，遇到 sentinel 则结束。被 `CancelledError` 取消时静默吞掉（仅取消消费）。
- **`_run_detached_sse_stream(agen_factory, *, log_ctx)`**：组合上面两者：
  1. 创建 `queue = asyncio.Queue()` 与 sentinel。
  2. `task = asyncio.create_task(_run_producer(agen_factory(), queue, sentinel, log_ctx))`，加入 `_BACKGROUND_TASKS`，并 `add_done_callback` 自动移除引用 + 记录"后台任务完成"日志。
  3. 返回 `_drain_queue(queue, sentinel)` 给 `StreamingResponse`。

最终接口体核心如下：

```python
async def _agen_factory() -> AsyncGenerator[str, None]:
    async for event in chat_service.stream_chat_events(
        chat_request,
        created_messages.user_message_id,
        created_messages.assistant_message_id,
        user_id=auth_info.user_id,
    ):
        yield event

return StreamingResponse(
    _run_detached_sse_stream(
        _agen_factory,
        log_ctx={
            "conversation_id": chat_request.conversation_id,
            "user_id": auth_info.user_id,
            "assistant_message_id": created_messages.assistant_message_id,
        },
    ),
    media_type="text/event-stream",
)
```

### 2. 不动的部分

- [chat_service.py](backend/app/services/chat/chat_service.py) 与 [chat_orchestrator.py](backend/app/services/chat/chat_orchestrator.py) 完全不变。生产任务里 `run_chat_turn` 自身的 `try/except` 已能把业务异常转成 `error` 事件并把后续 `persist_final_assistant_message`/`schedule_memory_write` 跑完。
- [post_process_service.py](backend/app/services/chat/post_process_service.py) 不变；`schedule_memory_write` 内部已经 `asyncio.create_task`。

## 关键细节

- **队列容量**：使用无界 `asyncio.Queue()`。后台任务一般完成后整个事件量是有限的（最多十几到几百个事件），无界更简单且不会阻塞生产侧。
- **取消语义**：消费侧被 Starlette 取消时，`_drain_queue` 内 `await queue.get()` 抛 `CancelledError`，我们 `contextlib.suppress(asyncio.CancelledError)` 安全退出；不触碰生产任务。
- **日志补充**：在 `chat.py` 内增加两条 INFO 级日志便于排查：
  - 客户端断开时（在 `_drain_queue` 的 `except CancelledError` 分支）："SSE consumer disconnected, producer continues"
  - 后台任务结束时（`add_done_callback`）："Background chat producer finished"，包含 `conversation_id`/`assistant_message_id`/`exception` 字段。
- **fire-and-forget**：根据您的选择，不在 lifespan 中等待这些后台任务，应用关闭由 uvicorn 自然取消即可。

## 验证步骤

1. 本地启动后端，前端发起一次问答；
2. 在助手回答中途关闭浏览器/标签页；
3. 观察后端日志：
   - 应出现 "SSE consumer disconnected, producer continues"；
   - 不再出现裸的 `CancelledError` 堆栈；
   - 出现 "Stream message generation completed"、"Assistant message updated"、"Background chat producer finished"；
4. 重新打开会话，确认中断的那条助手消息已经完整落库（DONE 状态）。
