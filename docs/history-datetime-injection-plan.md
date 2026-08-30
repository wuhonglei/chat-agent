# 历史消息时间注入方案

> **现网实现摘要（2026-08-30 对照代码）**
>
> 已落地的是 **当前轮冻结**，不是本文后半的「给每条历史 user 消息补时间」。
>
> | 项 | 现网 |
> |----|------|
> | 当前轮 `<current_datetime>` | `ChatOrchestrator` 用 `user_message.created_at` 调用 `get_current_datetime_str`，传入 `stream_session_events`；`ChatSessionAgent` 存 `_turn_datetime`，守卫重建复用已拼好的 `_user_message_content` |
> | 格式 | `YYYY-MM-DD HH:MM:SS 星期X`（中文星期，不依赖 locale） |
> | 历史 user 消息 | `format_chat_message_for_llm` **不**追加时间；历史仍是 `content_blocks` 纯文本 |
> | system prompt | **禁止**写入时间（前缀缓存实验：写入后命中率可掉到 0%） |
>
> 验证：`backend/tests/prompts/test_user_message_datetime.py`、`test_chat_orchestrator_tracing.py` 中的 `test_stream_passes_user_message_created_at_as_current_datetime`。
>
> 下文「实现方案 / 验证方案」描述的是尚未合入的历史注入，不要当成已上线行为。

## 背景

### 现状

当前 chat-agent 的时间注入只覆盖**当前轮次**：

```
系统提示词：  静态，无时间
历史 user 消息：  纯 content_blocks，无时间
当前轮 user 消息：  <current_datetime>2026-08-23 23:58:12</current_datetime>
```

发给 LLM 的完整消息列表：

```
[system]  <instructions>你是一个有帮助的智能助手。...</instructions>

[user]    之前的问题                              ← 无时间
[assistant] 之前的回答
[user]    更早的问题                              ← 无时间
[assistant] 更早的回答

[user]    <user_message>
            <query>当前问题</query>
          </user_message>
          <tool_call_context>
            <current_datetime>2026-08-23 23:58:12</current_datetime>
          </tool_call_context>
```

### 问题

模型无法从历史消息中感知时间线：
- 不知道"之前的问题"是 5 分钟前还是 3 天前问的
- 跨天场景下，无法区分"昨天的问题"和"今天的问题"
- 涉及时效性的问题（"今天有什么新闻"）在历史中失去时间锚点

### 目标

```
系统提示词：  不动（静态，无时间）
历史 user 消息：  content_blocks + <current_datetime>（从 DB created_at 提取）
当前轮 user 消息：  不动（保持现有完整 <tool_call_context> 格式）
```

优化后发给 LLM 的完整消息列表：

```
[system]  <instructions>你是一个有帮助的智能助手。...</instructions>

[user]    之前的问题
          <tool_call_context>
            <current_datetime>2026-08-23 23:55:10</current_datetime>
          </tool_call_context>
[assistant] 之前的回答
[user]    更早的问题
          <tool_call_context>
            <current_datetime>2026-08-23 22:30:45</current_datetime>
          </tool_call_context>
[assistant] 更早的回答

[user]    <user_message>
            <query>当前问题</query>
          </user_message>
          <tool_call_context>
            <current_datetime>2026-08-23 23:58:12</current_datetime>
          </tool_call_context>
```

---

## 方案调研：为什么选择 per-turn frozen 而不是 deer-flow 的 SystemMessage 注入

### 调研的 5 个项目

| 项目 | 时间位置 | 精度 | 更新频率 | 跨天处理 |
|------|---------|------|---------|---------|
| **deer-flow** | 消息 `<system-reminder>` | 天 | 首次+跨天 | ✅ 中间件检测+注入 |
| **Claude Code** | userContext + attachment | 天 | memoize + date_change | ✅ 尾部追加 |
| **Openencode** | 系统提示词 `<env>` | 天 | 每轮重建 | ✅ 自动（无缓存） |
| **Codex** | 环境 XML + developer msg | 秒 | 每轮+周期提醒 | ✅ 自动更新 |
| **DeepSeek Harness** | pre-step user/msg | 秒 | 每步节流 | ✅ 自动更新 |

### deer-flow 方案为什么不完全适合 chat-agent

deer-flow 的核心设计是**系统提示词完全静态 + 时间通过独立 SystemMessage 注入**，
这适合有 prefix cache 的长生命周期会话。但 chat-agent 有两个关键差异：

1. **系统提示词无状态重建** — 每次请求都重新 render Jinja2 模板，不存在跨用户的
   prefix cache，所以"保持系统提示词静态"这个动机不成立

2. **历史消息从 DB 加载** — deer-flow 用 LangGraph checkpoint 的 `additional_kwargs`
   挂元数据，扫描消息历史可以检测"上次注入的日期"。chat-agent 用 SQLModel 持久化，
   `content_blocks` 是 JSON 列，没有 `additional_kwargs` 通道

3. **消息角色交替约束** — deer-flow 用 SystemMessage 注入时间，但 chat-agent 的
   历史消息是 user/assistant 严格交替的，插入额外的 system 消息会破坏交替模式

### 为什么只补全 `<current_datetime>`，不注入 memory/RAG/uploads

| 字段 | 性质 | 是否注入历史 |
|------|------|------------|
| `<current_datetime>` | 不可变事实，不会过时 | ✅ 应该 |
| `<user_memories>` | 动态，每轮重新检索 | ❌ 不应该 |
| `<attachment_context>` (RAG) | 瞬时快照，KB 可能已更新 | ❌ 不应该 |
| `<attachment_uploads>` | 会话级状态，文件可能已删除 | ❌ 不应该 |

理由：
- RAG 搜索结果是瞬时快照，回放旧结果可能引用已不存在的文档
- Memory 每轮重新检索，回放旧 memory 与当前轮注入的 memory 重复且可能冲突
- 附件清单反映当前会话状态，历史附件可能已不相关
- 强行统一格式会增加 ~3000 token/轮 × N 轮的无效开销

---

## 实现方案

### 改动范围

仅需改动 **2 个文件**，不改 DB schema，不改 metadata，不改当前轮逻辑。

#### 文件 1：`backend/app/protocols/chat_messages.py`

**改动点：** `format_chat_message_for_llm` 函数

**改动内容：** 当格式化历史 user 消息时，从 `message.created_at` 提取时间，
追加 `<tool_call_context><current_datetime>` 到 content 末尾。

**改动前：**
```python
def format_chat_message_for_llm(
    message: ChatMessageWithToolCalls,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    # ... 现有逻辑：从 content_blocks 提取 content
    payload = {"role": role, "content": content}
    return payload
```

**改动后：**
```python
def format_chat_message_for_llm(
    message: ChatMessageWithToolCalls,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    # ... 现有逻辑：从 content_blocks 提取 content

    # 对历史 user 消息，从 created_at 追加时间上下文
    if role == "user" and hasattr(message, "created_at") and message.created_at:
        created_at = message.created_at
        if isinstance(created_at, str):
            # 已经是字符串格式，直接使用（截取到秒）
            dt_str = created_at[:19].replace("T", " ")
        else:
            # datetime 对象，格式化为 %Y-%m-%d %H:%M:%S
            dt_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = (
            f"{content}\n\n"
            f"<tool_call_context>\n"
            f"  <current_datetime>{dt_str}</current_datetime>\n"
            f"</tool_call_context>"
        )

    payload = {"role": role, "content": content}
    return payload
```

**关键设计决策：**

1. **复用现有 `<current_datetime>` 标签** — 与当前轮消息格式一致，模型已经
   理解这个标签的含义

2. **不注入 `<user_message>` 包装** — 历史消息的 content_blocks 已经是原始内容，
   外层不需要再包 `<user_message><query>` 标签。`<current_datetime>` 直接追加
   在原始内容末尾即可

3. **只处理 role == "user"** — assistant 消息不需要时间（回复时间不重要，
   用户提问时间才有语义价值）

4. **不处理 tool 消息** — tool 结果是瞬时的，时间戳对模型无意义

#### 文件 2：`backend/app/protocols/chat_messages.py`（同一文件，辅助函数）

**改动点：** 提取时间格式化为独立函数，供 `format_chat_message_for_llm` 调用。

```python
def _format_created_at_for_context(created_at: Any) -> str | None:
    """从消息的 created_at 字段提取格式化时间字符串。

    返回格式：'YYYY-MM-DD HH:MM:SS'，用于注入 <current_datetime>。
    返回 None 表示无法提取（跳过注入）。
    """
    if created_at is None:
        return None
    if isinstance(created_at, str):
        # 字符串格式，截取到秒
        return created_at[:19].replace("T", " ")
    # datetime 对象
    try:
        return created_at.strftime("%Y-%m-%d %H:%M:%S")
    except (AttributeError, ValueError):
        return None
```

---

## 不需要改动的部分

| 组件 | 原因 |
|------|------|
| `system_prompt.py` | 系统提示词保持静态，不注入时间 |
| `prompt_utils.py` | `get_user_message_for_tool_calls` 不变，当前轮逻辑不动 |
| `chat_session_agent.py` | `_turn_datetime` 冻结逻辑不动 |
| `base.py` | `_compose_history_messages` 不变，它调用 `format_chat_message_for_llm` |
| `message_db.py` | 不改 DB schema，`created_at` 字段已存在 |
| `chat.py` (API 层) | 不改接口 |

---

## 改动前后对比

### 改动前：模型看到的消息

```
[user]    今天天气怎么样
[assistant] 我来帮你查一下...
[user]    上海呢
[assistant] 上海今天晴...
[user]    <user_message><query>帮我写个 Python 脚本</query></user_message>
          <tool_call_context>
            <current_datetime>2026-08-24 00:05:03</current_datetime>
          </tool_call_context>
```

模型视角：不知道"今天天气怎么样"是什么时候问的，可能是刚才也可能是昨天。

### 改动后：模型看到的消息

```
[user]    今天天气怎么样
          <tool_call_context>
            <current_datetime>2026-08-23 23:55:10</current_datetime>
          </tool_call_context>
[assistant] 我来帮你查一下...
[user]    上海呢
          <tool_call_context>
            <current_datetime>2026-08-23 23:56:30</current_datetime>
          </tool_call_context>
[assistant] 上海今天晴...
[user]    <user_message><query>帮我写个 Python 脚本</query></user_message>
          <tool_call_context>
            <current_datetime>2026-08-24 00:05:03</current_datetime>
          </tool_call_context>
```

模型视角：明确知道"今天天气怎么样"是 2026-08-23 23:55 问的，
"帮我写个脚本"是 2026-08-24 00:05 问的，跨越了午夜。

---

## 风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| Token 增量 | 低 | 每条历史 user 消息增加 ~50 token（`<tool_call_context><current_datetime>...</current_datetime></tool_call_context>`），10 轮历史 ≈ 500 token |
| 格式兼容性 | 低 | 复用现有 `<current_datetime>` 标签，模型已理解 |
| 回归风险 | 低 | 只改 `format_chat_message_for_llm` 一个函数，不影响当前轮逻辑、DB schema、API 接口 |
| assistant 消息重复注入 | 无 | 只处理 `role == "user"`，assistant 消息不受影响 |

---

## 验证方案

### 1. 单元测试

在 `backend/tests/protocols/` 下新增测试：

```python
def test_format_chat_message_for_llm_injects_datetime():
    """历史 user 消息应注入 <current_datetime>"""
    msg = ChatMessage(
        id="test-1",
        conversation_id="conv-1",
        role="user",
        content_blocks=[TextBlock(type="text", text="你好")],
        created_at=datetime(2026, 8, 23, 23, 55, 10),
    )
    result = format_chat_message_for_llm(msg)
    assert "<current_datetime>2026-08-23 23:55:10</current_datetime>" in result["content"]
    assert result["role"] == "user"


def test_format_chat_message_for_llm_assistant_no_datetime():
    """历史 assistant 消息不应注入时间"""
    msg = ChatMessage(
        id="test-2",
        conversation_id="conv-1",
        role="assistant",
        content_blocks=[TextBlock(type="text", text="你好")],
        created_at=datetime(2026, 8, 23, 23, 55, 30),
    )
    result = format_chat_message_for_llm(msg)
    assert "<current_datetime>" not in result["content"]
```

### 2. E2E 验证

1. 创建一个会话，发送第一条消息
2. 等待几秒，发送第二条消息
3. 检查 LLM 请求的 messages 列表，确认历史 user 消息包含 `<current_datetime>`
4. 跨天场景：模拟 created_at 跨越午夜的消息序列，确认时间正确

### 3. Langfuse 验证

在 Langfuse trace 中检查 `chat-turn` span 的 input messages，确认：
- 历史 user 消息包含 `<current_datetime>`
- assistant 消息不包含
- 当前轮消息格式不变
