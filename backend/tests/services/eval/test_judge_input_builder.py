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
    query, memories, attachment, tools = parse_generation_messages(messages)
    assert query == "当前问题"
    assert memories == ["m1"]
    assert attachment == "rag"
    assert tools == ["tool result A", "tool result B"]


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


def test_build_reference_xml_truncates() -> None:
    ref = build_reference_xml(
        tool_contents=["x" * 20_000],
        max_chars=500,
    )
    assert len(ref) <= 500 + 50  # 允许结尾标签少量余量
    assert "truncated" in ref


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
