"""JudgeInputBuilder 解析与降级单元测试。"""

from __future__ import annotations

from typing import Any

from app.services.eval.judge_input_builder import (
    JudgeInputBuilder,
    build_judge_query,
    build_reference_xml,
    parse_generation_messages,
    parse_user_xml,
)


def test_parse_user_xml_extracts_query_memories_and_attachment() -> None:
    content = """
<user_message>
  <query>FastMCP 4 有什么新特性？</query>
  <attachment_context>
    <attachment><content>kb snippet</content></attachment>
  </attachment_context>
</user_message>
<tool_call_context>
  <user_memories>
    <memory_item>
      <memory>用户关注 Python MCP</memory>
      <relevance>高</relevance>
    </memory_item>
  </user_memories>
</tool_call_context>
"""
    query, memories, attachment = parse_user_xml(content)
    assert query == "FastMCP 4 有什么新特性？"
    assert memories == ["用户关注 Python MCP"]
    assert "kb snippet" in attachment


def test_parse_generation_messages_uses_last_structured_user() -> None:
    messages = [
        {"role": "system", "content": "instructions"},
        {
            "role": "user",
            "content": "<user_message><query>历史问题</query></user_message>",
        },
        {"role": "assistant", "content": "旧回答"},
        {
            "role": "user",
            "content": (
                "<user_message><query>当前问题</query>"
                "<attachment_context>rag</attachment_context></user_message>"
                "<tool_call_context><user_memories>"
                "<memory_item><memory>m1</memory></memory_item>"
                "</user_memories></tool_call_context>"
            ),
        },
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
        {"role": "tool", "content": "tool result A"},
        {"role": "tool", "content": "tool result B"},
    ]
    query, memories, attachment, tools, images, dialogue_history = (
        parse_generation_messages(messages)
    )
    assert query == "当前问题"
    assert memories == ["m1"]
    assert attachment == "rag"
    assert tools == ["tool result A", "tool result B"]
    assert images == []
    # 历史轮 user/assistant 进 dialogue_history，本轮消息不进
    assert "<dialogue_history>" in dialogue_history
    assert "历史问题" in dialogue_history
    assert "旧回答" in dialogue_history
    assert "当前问题" not in dialogue_history
    assert "tool result A" not in dialogue_history


def test_parse_generation_messages_history_tools_excluded_from_reference() -> None:
    """历史轮工具返回不混入本轮参考资料（以胜出消息为界）。"""
    messages = [
        {
            "role": "user",
            "content": "<user_message><query>历史问题</query></user_message>",
        },
        {"role": "assistant", "content": None, "tool_calls": [{"id": "h1"}]},
        {"role": "tool", "content": "hist-tool-result"},
        {"role": "assistant", "content": "历史回答"},
        {
            "role": "user",
            "content": "<user_message><query>本轮问题</query></user_message>",
        },
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "content": "cur-tool-result"},
    ]
    query, _, _, tools, _, dialogue_history = parse_generation_messages(messages)
    assert query == "本轮问题"
    assert tools == ["cur-tool-result"]
    assert "hist-tool-result" not in dialogue_history
    assert "历史回答" in dialogue_history


def test_parse_generation_messages_history_images_annotated() -> None:
    """历史轮图片不带入本轮，但在历史文本中标注存在图片。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "<user_message><query>看看这张图</query></user_message>"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,OLDIMAGE"},
                },
            ],
        },
        {"role": "assistant", "content": "这是一张猫的照片"},
        {
            "role": "user",
            "content": "<user_message><query>它是什么颜色</query></user_message>",
        },
    ]
    query, _, _, _, images, dialogue_history = parse_generation_messages(messages)
    assert query == "它是什么颜色"
    assert images == []  # 历史图不进本轮图片输入
    assert "看看这张图" in dialogue_history
    assert "[该消息附带 1 张图片，未随评估提供]" in dialogue_history
    assert "这是一张猫的照片" in dialogue_history


def test_parse_generation_messages_keeps_winner_images() -> None:
    """图片归属「提供 query 的 user 消息」，历史轮图片不串台。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "<user_message><query>历史问题</query></user_message>"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,OLDIMAGE"},
                },
            ],
        },
        {"role": "assistant", "content": "旧回答"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "<user_message><query>这是什么</query></user_message>"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "@@@langfuseMedia:type=image/jpeg"
                            "|id=QFKfQFDG8qvj6r03Ci0MDe|source=base64_data_uri@@@"
                        )
                    },
                },
            ],
        },
    ]
    query, _, _, _, images, _ = parse_generation_messages(messages)
    assert query == "这是什么"
    assert images == [
        "@@@langfuseMedia:type=image/jpeg|id=QFKfQFDG8qvj6r03Ci0MDe|source=base64_data_uri@@@"
    ]


def test_parse_generation_messages_image_only_falls_back_to_last_images() -> None:
    """图片单独成块、无文本 query 时，回退到最后一条带图 user 消息。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,ONLY"}}
            ],
        },
    ]
    query, _, _, _, images, _ = parse_generation_messages(messages)
    assert query == ""
    assert images == ["data:image/png;base64,ONLY"]


def test_build_judge_query_and_reference_xml() -> None:
    q = build_judge_query("hello", ["mem-a"])
    assert "hello" in q
    assert "<user_memories>" in q
    assert "mem-a" in q

    ref = build_reference_xml(
        attachment_context="att",
        tool_contents=["t1", "t2"],
    )
    assert ref.startswith("<参考资料>")
    assert "<attachment_context>" in ref
    assert "t1" in ref
    assert "t2" in ref


def test_build_reference_xml_keeps_full_content() -> None:
    long_content = "x" * 20_000
    ref = build_reference_xml(tool_contents=[long_content, "t2"])
    assert long_content in ref
    assert "t2" in ref
    assert "truncated" not in ref


class _FakeObs:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def model_dump(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _FakeObservationsApi:
    def __init__(self, data: list[Any]) -> None:
        self._data = data

    def get_many(self, **kwargs: Any) -> Any:
        assert kwargs.get("trace_id")
        return type("Resp", (), {"data": self._data})()


class _FakeLangfuse:
    def __init__(self, data: list[Any]) -> None:
        self.api = type(
            "Api", (), {"observations": _FakeObservationsApi(data)}
        )()


def test_builder_from_last_generation() -> None:
    user_xml = (
        "<user_message><query>q1</query>"
        "<attachment_context>rag-body</attachment_context></user_message>"
        "<tool_call_context><user_memories>"
        "<memory_item><memory>mem</memory></memory_item>"
        "</user_memories></tool_call_context>"
    )
    gen = _FakeObs(
        type="GENERATION",
        start_time="2026-01-02T00:00:00Z",
        input={
            "messages": [
                {"role": "user", "content": user_xml},
                {"role": "tool", "content": "tool-out"},
            ],
            "tools": [{"name": "ignored"}],
        },
        output={"content": "final answer"},
    )
    older = _FakeObs(
        type="GENERATION",
        start_time="2026-01-01T00:00:00Z",
        input={"messages": [{"role": "user", "content": "<query>old</query>"}]},
        output="old",
    )
    builder = JudgeInputBuilder(
        langfuse_client=_FakeLangfuse([gen, older]),
    )
    result = builder.build_from_trace(
        {
            "id": "trace-1",
            "input": "chat-turn-query",
            "output": "chat-turn-answer",
            "metadata": {},
        }
    )
    assert "q1" in result.query
    assert "<user_memories>" in result.query
    assert "mem" in result.query
    assert result.answer == "final answer"
    assert "rag-body" in result.reference_xml
    assert "tool-out" in result.reference_xml
    assert result.source_flags["last_generation"] is True
    assert result.source_flags["has_memories"] is True
    assert result.source_flags["tool_count"] == 1
    assert result.images == []
    assert result.source_flags["image_count"] == 0
    assert result.source_flags["image_failed"] == 0
    assert result.dialogue_history == ""
    assert result.source_flags["history_turns"] == 0


def test_builder_resolves_images_from_generation(
    monkeypatch: Any,
) -> None:
    """GENERATION input 里的图片引用解析为 data URI 并进入 JudgeInput.images。"""
    media_marker = (
        "@@@langfuseMedia:type=image/jpeg"
        "|id=QFKfQFDG8qvj6r03Ci0MDe|source=base64_data_uri@@@"
    )
    gen = _FakeObs(
        type="GENERATION",
        start_time="2026-01-02T00:00:00Z",
        input={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "<user_message><query>这是什么</query></user_message>",
                        },
                        {"type": "image_url", "image_url": {"url": media_marker}},
                    ],
                },
            ],
        },
        output={"content": "一张户口簿照片"},
    )
    builder = JudgeInputBuilder(langfuse_client=_FakeLangfuse([gen]))

    seen: list[list[str]] = []

    def _fake_resolve(refs: list[str]) -> list[str]:
        seen.append(refs)
        # 模拟解析成功返回 data URI
        return ["data:image/jpeg;base64,RESOLVED"]

    monkeypatch.setattr(
        "app.services.eval.judge_input_builder.resolve_image_refs",
        _fake_resolve,
    )
    result = builder.build_from_trace(
        {
            "id": "trace-3",
            "input": "这是什么",
            "output": "一张户口簿照片",
            "metadata": {},
        }
    )
    assert seen == [[media_marker]]
    assert result.images == ["data:image/jpeg;base64,RESOLVED"]
    assert result.source_flags["image_count"] == 1


def test_builder_falls_back_to_chat_turn_when_no_generation() -> None:
    builder = JudgeInputBuilder(langfuse_client=_FakeLangfuse([]))
    result = builder.build_from_trace(
        {
            "id": "trace-2",
            "input": "plain query",
            "output": "plain answer",
            "metadata": {},
        }
    )
    assert result.query == "plain query"
    assert result.answer == "plain answer"
    assert result.reference_xml == ""
    assert result.source_flags["chat_turn_only"] is True
    assert result.source_flags["last_generation"] is False
