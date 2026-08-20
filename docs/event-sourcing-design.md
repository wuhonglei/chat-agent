# Event Sourcing 设计方案 — chat-agent 对话日志

## 1. 背景与动机

### 当前问题

chat-agent 的对话存储是 **终态模型**：只持久化 user/assistant 两条消息，中间过程丢失。

```
MessageDb 表:
  id | conversation_id | role      | content_blocks          | status
  ---|-----------------|-----------|-------------------------|-------
  1  | conv-abc        | user      | [{type: text, text: ..}] | done
  2  | conv-abc        | assistant | [{type: text, text: ..}] | done
```

丢失的中间过程：
- 本轮调用了哪些工具、参数是什么、返回了什么
- 上下文守卫触发了几级降级、压缩了多少 token
- guardrail 熔断了哪些调用、原因是什么
- 模型的流式 token（assistant/chunk）— 无法 replay
- 请求时的 provider/model 配置 — 无法事后追溯

### 借鉴目标

DeepSeek Harness 的 Session Event Sourcing：所有状态变更为不可变事件，append-only 日志是唯一真相源。

## 2. 事件类型定义

```python
# app/events/types.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionEventType(str, Enum):
    """对话事件类型 — 9 种核心事件"""

    # ── 回合边界 ──
    TURN_START = "turn/start"
    TURN_END = "turn/end"

    # ── 步骤边界 (一轮 LLM 调用 + 工具执行) ──
    STEP_START = "step/start"
    STEP_END = "step/end"

    # ── 用户输入 ──
    USER_MESSAGE = "user/message"

    # ── 模型输出 ──
    ASSISTANT_CHUNK = "assistant/chunk"      # 流式 token
    ASSISTANT_MESSAGE = "assistant/message"   # 完整回复

    # ── 工具调用 ──
    TOOL_CALL = "tool/call"
    TOOL_RESULT = "tool/result"

    # ── 请求配置 ──
    REQUEST_HEADER = "request/header"        # 完整配置快照
    REQUEST_CONTEXT = "request/context"      # provider/model

    # ── 扩展事件 (chat-agent 特有) ──
    GUARDRAIL_ACTION = "guardrail/action"    # 熔断/阻断记录
    CONTEXT_GUARD = "context/guard"          # 上下文守卫降级记录
    COMPACTION = "compaction"                # 压缩记录


@dataclass(frozen=True)
class SessionEvent:
    """不可变对话事件 — 追加到日志后永不修改"""

    type: SessionEventType
    seq: int                    # 单调递增序号
    time: float                 # Unix timestamp
    turn: int                   # 所属回合号
    step: int | None = None     # 所属步骤号 (turn 内)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "seq": self.seq,
            "time": self.time,
            "turn": self.turn,
            "step": self.step,
            "data": self.data,
        }
```

## 3. 事件数据结构

### turn/start & turn/end

```python
# turn/start
{
    "type": "turn/start",
    "seq": 0,
    "time": 1718800000.0,
    "turn": 1,
    "data": {
        "user_id": "u-123",
        "conversation_id": "conv-abc",
        "agent_mode": 1,
        "think_mode": False,
    }
}

# turn/end
{
    "type": "turn/end",
    "seq": 25,
    "time": 1718800450.0,
    "turn": 1,
    "data": {
        "reason": "completed",  # completed | stopped | failed | aborted
        "total_steps": 3,
        "total_tool_calls": 5,
        "duration_ms": 450000,
    }
}
```

### step/start & step/end

```python
# step/start
{
    "type": "step/start",
    "seq": 1,
    "time": 1718800001.0,
    "turn": 1,
    "step": 1,
    "data": {}
}

# step/end
{
    "type": "step/end",
    "seq": 10,
    "time": 1718800030.0,
    "turn": 1,
    "step": 1,
    "data": {
        "end_reason": "completed",  # completed | max-iterations | guardrail-halt
        "tool_calls_in_step": 2,
    }
}
```

### user/message

```python
{
    "type": "user/message",
    "seq": 2,
    "time": 1718800002.0,
    "turn": 1,
    "step": 1,
    "data": {
        "message_id": "msg-user-001",
        "content_blocks": [
            {"type": "text", "text": "帮我查一下今天的天气"}
        ],
        "attachments": [],  # 附件引用
        "memories_injected": 3,  # 注入的记忆条数
    }
}
```

### assistant/chunk (流式 token)

```python
{
    "type": "assistant/chunk",
    "seq": 3,
    "time": 1718800003.0,
    "turn": 1,
    "step": 1,
    "data": {
        "delta": {"content": "好的", "role": "assistant"},
        "chunk_index": 0,
    }
}
```

> 流式 token 数量大，考虑：(a) 不落库仅内存广播给 SSE；(b) 落库但用批量写入；(c) 只记录首尾 chunk + 总量。

### assistant/message (完整回复)

```python
{
    "type": "assistant/message",
    "seq": 8,
    "time": 1718800010.0,
    "turn": 1,
    "step": 1,
    "data": {
        "message_id": "msg-asst-001",
        "content_blocks": [
            {"type": "text", "text": "今天深圳天气晴朗..."},
            {"type": "tool_use", "tool_call_id": "call-1", "name": "tavily_web_search", ...}
        ],
        "reasoning": "",  # thinking 内容
        "usage": {
            "prompt_tokens": 1200,
            "completion_tokens": 350,
            "total_tokens": 1550,
        },
    }
}
```

### tool/call

```python
{
    "type": "tool/call",
    "seq": 4,
    "time": 1718800004.0,
    "turn": 1,
    "step": 1,
    "data": {
        "tool_call_id": "call-1",
        "name": "tavily_web_search",
        "arguments": {"queries": ["深圳今天天气"]},
        "server_name": "tavily",
    }
}
```

### tool/result

```python
{
    "type": "tool/result",
    "seq": 5,
    "time": 1718800008.0,
    "turn": 1,
    "step": 1,
    "data": {
        "tool_call_id": "call-1",
        "name": "tavily_web_search",
        "is_error": False,
        "content": "{\"results\": [...]}",
        "content_length": 2048,
        "was_compressed": False,
        "duration_ms": 3500,
    }
}
```

### request/header

```python
{
    "type": "request/header",
    "seq": 6,
    "time": 1718800009.0,
    "turn": 1,
    "step": 2,
    "data": {
        "provider": "dashscope",
        "model": "qwen3-max",
        "max_tokens": 8192,
        "temperature": 0.7,
        "system_prompt_length": 2500,
        "tools_count": 12,
        "context_window": 131072,
    }
}
```

### request/context

```python
{
    "type": "request/context",
    "seq": 7,
    "time": 1718800009.5,
    "turn": 1,
    "step": 2,
    "data": {
        "provider": "dashscope",
        "model": "qwen3-max",
        "context_window": 131072,
    }
}
```

### guardrail/action (chat-agent 特有)

```python
{
    "type": "guardrail/action",
    "seq": 9,
    "time": 1718800020.0,
    "turn": 1,
    "step": 1,
    "data": {
        "action": "block",          # block | halt | warn
        "reason": "exact_failure",  # exact_failure | same_tool_failure | no_progress
        "tool_name": "tavily_web_search",
        "arguments": {"queries": ["深圳天气"]},
        "failure_count": 5,
        "message": "已阻断：相同参数连续失败 5 次",
    }
}
```

### context/guard (chat-agent 特有)

```python
{
    "type": "context/guard",
    "seq": 11,
    "time": 1718800025.0,
    "turn": 1,
    "step": 1,
    "data": {
        "trigger": "pressure",           # pressure | overflow
        "level": "size_aware_compress",  # compress_history | window_summary | size_aware | stop_tools
        "total_tokens_before": 95000,
        "threshold": 80000,
        "tokens_saved": 15000,
        "messages_affected": 3,
    }
}
```

### compaction (chat-agent 特有)

```python
{
    "type": "compaction",
    "seq": 12,
    "time": 1718800026.0,
    "turn": 1,
    "step": 1,
    "data": {
        "tool_call_id": "call-2",
        "tool_name": "tavily_web_pages_extract",
        "original_content_length": 15000,
        "compressed_content_length": 3000,
        "compression_ratio": 0.2,
        "method": "head_tail_truncate",  # head_tail_truncate | llm_summarize | semantic_compress
    }
}
```

## 4. 架构设计

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     ChatSessionAgent                        │
│                                                             │
│  stream_session_events()                                    │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  EventLog   │───▶│ EventStore   │───▶│ EventConsumer │  │
│  │ (内存追加)   │    │ (持久化)      │    │ (投影/广播)    │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
│       │                  │                     │            │
│       │                  ▼                     ▼            │
│       │            ┌──────────┐         ┌───────────┐      │
│       │            │ Postgres │         │ SSE 推送   │      │
│       │            │ event_log│         │ (可选)     │      │
│       │            └──────────┘         └───────────┘      │
│       │                                                     │
│       ▼                                                     │
│  derive_messages()  ← 从 event log 投影出 LLM 消息列表       │
│  derive_session()   ← 从 event log 投影出完整会话视图         │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 EventLog — 内存事件日志

```python
# app/events/event_log.py

import time
from typing import Any, Callable

from app.events.types import SessionEvent, SessionEventType


class EventLog:
    """单会话的 append-only 事件日志。

    生命周期与一个 ChatSessionAgent 绑定。
    事件追加后不可修改（frozen dataclass）。
    """

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self._events: list[SessionEvent] = []
        self._seq = 0
        self._current_turn = 0
        self._current_step: int | None = None
        self._listeners: list[Callable[[SessionEvent], None]] = []

    @property
    def events(self) -> list[SessionEvent]:
        return list(self._events)

    @property
    def seq(self) -> int:
        return self._seq

    def on_append(self, listener: Callable[[SessionEvent], None]) -> None:
        """注册事件追加监听器 (用于实时广播)"""
        self._listeners.append(listener)

    def append(
        self,
        event_type: SessionEventType,
        data: dict[str, Any] | None = None,
    ) -> SessionEvent:
        """追加一个事件，返回不可变的事件对象。"""
        event = SessionEvent(
            type=event_type,
            seq=self._seq,
            time=time.time(),
            turn=self._current_turn,
            step=self._current_step,
            data=data or {},
        )
        self._events.append(event)
        self._seq += 1

        # 更新内部状态
        if event_type == SessionEventType.TURN_START:
            self._current_turn = event.data.get("turn", self._current_turn + 1)
            self._current_step = None
        elif event_type == SessionEventType.STEP_START:
            self._current_step = event.data.get("step", (self._current_step or 0) + 1)
        elif event_type == SessionEventType.STEP_END:
            self._current_step = None

        # 广播给监听器
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # 监听器失败不影响日志

        return event

    def derive_messages(self) -> list[dict[str, Any]]:
        """从事件日志投影出 LLM 消息列表。

        等价于 DeepSeek Harness 的 session.deriveMessages()。
        只提取 user/message 和 assistant/message 事件，
        跳过 turn/step 边界和 guardrail 事件。
        """
        messages: list[dict[str, Any]] = []
        for event in self._events:
            match event.type:
                case SessionEventType.USER_MESSAGE:
                    messages.append({
                        "role": "user",
                        "content": event.data.get("content_blocks", []),
                    })
                case SessionEventType.ASSISTANT_MESSAGE:
                    blocks = event.data.get("content_blocks", [])
                    # 提取 tool_calls 用于 LLM 格式
                    tool_calls = [
                        b for b in blocks if b.get("type") == "tool_use"
                    ]
                    text_parts = [
                        b.get("text", "") for b in blocks if b.get("type") == "text"
                    ]
                    msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": "\n".join(text_parts) or None,
                    }
                    if tool_calls:
                        msg["tool_calls"] = tool_calls
                    messages.append(msg)
                case SessionEventType.TOOL_RESULT:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": event.data.get("tool_call_id"),
                        "content": event.data.get("content", ""),
                    })
        return messages

    def derive_tool_round(self) -> list[dict[str, Any]]:
        """投影当前轮的 tool/call + tool/result 对。"""
        result: list[dict[str, Any]] = []
        for event in self._events:
            if event.type == SessionEventType.TOOL_CALL:
                result.append({
                    "type": "tool_call",
                    "tool_call_id": event.data.get("tool_call_id"),
                    "name": event.data.get("name"),
                    "arguments": event.data.get("arguments"),
                })
            elif event.type == SessionEventType.TOOL_RESULT:
                result.append({
                    "type": "tool_result",
                    "tool_call_id": event.data.get("tool_call_id"),
                    "content": event.data.get("content"),
                    "is_error": event.data.get("is_error", False),
                })
        return result

    def derive_guardrail_actions(self) -> list[dict[str, Any]]:
        """投影所有 guardrail 干预记录。"""
        return [
            event.data for event in self._events
            if event.type == SessionEventType.GUARDRAIL_ACTION
        ]

    def derive_context_guards(self) -> list[dict[str, Any]]:
        """投影所有上下文守卫降级记录。"""
        return [
            event.data for event in self._events
            if event.type == SessionEventType.CONTEXT_GUARD
        ]
```

### 4.3 持久化层 — event_log 表

```sql
-- 新增表：对话事件日志 (与 messages 表共存，不替换)
CREATE TABLE conversation_events (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    event_type      VARCHAR(32) NOT NULL,  -- 'turn/start', 'tool/call', etc.
    seq             INTEGER NOT NULL,      -- 会话内单调递增
    turn            INTEGER NOT NULL,
    step            INTEGER,
    time            DOUBLE PRECISION NOT NULL,  -- Unix timestamp
    data            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(conversation_id, seq)
);

CREATE INDEX idx_events_conversation ON conversation_events(conversation_id, seq);
CREATE INDEX idx_events_type ON conversation_events(conversation_id, event_type);
```

### 4.4 EventConsumer — 消费者接口

```python
# app/events/consumers.py

from abc import ABC, abstractmethod
from app.events.types import SessionEvent


class EventConsumer(ABC):
    """事件消费者基类。"""

    @abstractmethod
    async def on_event(self, event: SessionEvent) -> None:
        """处理一个追加的事件。"""
        ...


class PersistenceConsumer(EventConsumer):
    """持久化消费者：批量写入 event_log 表。"""

    async def on_event(self, event: SessionEvent) -> None:
        # 批量缓冲，每 N 条或 turn/end 时 flush
        ...


class SSEBroadcastConsumer(EventConsumer):
    """SSE 广播消费者：将事件推送给前端。"""

    async def on_event(self, event: SessionEvent) -> None:
        # assistant/chunk → SSE stream chunk
        # tool/call → SSE tool_call_start event
        # tool/result → SSE tool_result event
        ...


class LangfuseConsumer(EventConsumer):
    """Langfuse 可观测消费者：记录到 Langfuse trace。"""

    async def on_event(self, event: SessionEvent) -> None:
        # tool/call → Langfuse span
        # tool/result → span output
        # context/guard → Langfuse score
        ...
```

## 5. 集成方案

### 5.1 与现有 ChatSessionAgent 集成

在 `stream_session_events` 中注入事件追加：

```python
# 修改 app/agents/chat_session_agent.py

class ChatSessionAgent(BaseAgent):
    def __init__(self, ...):
        ...
        self._event_log: EventLog | None = None

    async def stream_session_events(self, ...):
        # 初始化事件日志
        self._event_log = EventLog(conversation_id)

        # ── turn/start ──
        self._event_log.append(SessionEventType.TURN_START, {
            "user_id": user_id,
            "agent_mode": chat_request.agent_mode,
        })

        # ... 现有逻辑 ...

        for iteration in range(max_total_iterations):
            # ── step/start ──
            self._event_log.append(SessionEventType.STEP_START, {
                "step": iteration + 1,
            })

            # ── request/header (每次 LLM 调用前) ──
            self._event_log.append(SessionEventType.REQUEST_HEADER, {
                "provider": self.model_config.provider,
                "model": self.model_config.model_name,
                "max_tokens": self.model_config.max_output_tokens,
                "system_prompt_length": len(self._system_prompt),
                "tools_count": len(tools_list),
                "context_window": self.model_config.context_limit,
            })

            # ── 上下文守卫 ──
            action, base_prompt_messages = await self.unified_context_guard(...)
            # unified_context_guard 内部每级降级都 append CONTEXT_GUARD

            # ── 工具调用循环 ──
            # tool_executor 内部 append TOOL_CALL / TOOL_RESULT

            # ── step/end ──
            self._event_log.append(SessionEventType.STEP_END, {
                "end_reason": "completed" if round_state.is_final_answer_complete else "tool_round",
            })

        # ── turn/end ──
        self._event_log.append(SessionEventType.TURN_END, {
            "reason": "completed",
            "total_steps": iteration + 1,
        })
```

### 5.2 与 ToolExecutor 集成

```python
# 修改 app/agents/tool_executor.py

async def execute_single_tool(self, ...) -> ToolResultMessage:
    # ── tool/call ──
    event_log.append(SessionEventType.TOOL_CALL, {
        "tool_call_id": tool_call.id,
        "name": tool_name,
        "arguments": arguments,
        "server_name": server_name,
    })

    # ... 现有执行逻辑 ...

    # ── tool/result ──
    event_log.append(SessionEventType.TOOL_RESULT, {
        "tool_call_id": tool_call.id,
        "name": tool_name,
        "is_error": not success,
        "content_length": len(content),
        "was_compressed": content != original_content,
        "duration_ms": duration,
    })

    # ── guardrail/action (如果有干预) ──
    if guardrail_decision.kind != "allow":
        event_log.append(SessionEventType.GUARDRAIL_ACTION, {
            "action": guardrail_decision.kind.value,
            "tool_name": tool_name,
            "failure_count": failure_count,
            "message": guardrail_decision.message,
        })
```

### 5.3 与 unified_context_guard 集成

```python
# 修改 ChatSessionAgent.unified_context_guard

async def unified_context_guard(self, ...):
    # Step 2: compress history tool results
    if was_compressed:
        self._event_log.append(SessionEventType.CONTEXT_GUARD, {
            "trigger": "pressure",
            "level": "compress_history",
            "total_tokens_before": total_tokens,
            "tokens_saved": tokens_before - tokens_after,
        })

    # Step 3: window out-of-window summary
    if out_of_window:
        self._event_log.append(SessionEventType.CONTEXT_GUARD, {
            "trigger": "pressure",
            "level": "window_summary",
            "total_tokens_before": total_tokens,
            "messages_moved_out": len(out_of_window),
        })

    # Step 4: size-aware compress
    if was_size_compressed:
        self._event_log.append(SessionEventType.CONTEXT_GUARD, {
            "trigger": "pressure",
            "level": "size_aware_compress",
            "tokens_saved": tokens_before - tokens_after,
        })

    # Step 5: stop tools
    if action == "stop_tools":
        self._event_log.append(SessionEventType.CONTEXT_GUARD, {
            "trigger": "pressure",
            "level": "stop_tools",
            "total_tokens": total_tokens,
            "threshold": threshold,
        })
```

## 6. 迁移策略

### 阶段 1: 内存事件日志 (不改存储)

- 实现 EventLog + SessionEvent 类型
- 在 ChatSessionAgent 中集成 append 调用
- 实现 derive_messages() 替代现有的手动消息拼装
- **不改 messages 表**，事件日志仅用于运行时投影

### 阶段 2: 可选持久化

- 创建 conversation_events 表
- 实现 PersistenceConsumer
- 通过配置开关控制是否持久化事件
- messages 表继续作为前端展示的投影

### 阶段 3: 衍生能力

- eval replay: 从 event log 精确重放对话
- 可观测性: guardrail/context guard 事件 → Langfuse
- 调试: 完整的工具调用链追踪
- 压缩质量分析: 对比原始 tool/result 与压缩后内容

## 7. 与 DeepSeek Harness 的差异

| 维度 | DeepSeek Harness | chat-agent 方案 |
|------|-----------------|----------------|
| 语言 | TypeScript | Python |
| 存储 | SQLite/JSONL append-only | Postgres JSONB + messages 表共存 |
| 流式 token | 全量 assistant/chunk 持久化 | 可选：全量/首尾/不记录 |
| surface 概念 | 有 (replace 语义) | 无 (直接 derive) |
| 事件消费者 | Cordis 效果系统 | 简单监听器列表 |
| 并发安全 | Cordis fiber 生命周期 | asyncio.Lock (单线程) |
| 压缩事务 | compaction/start/end 锁 | 简化：单次操作无需事务 |
