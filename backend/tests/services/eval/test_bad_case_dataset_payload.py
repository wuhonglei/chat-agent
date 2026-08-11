"""BadCaseService.add_to_dataset payload 组装测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.models.bad_case_item_db import BadCaseItemDb
from app.services.eval.bad_case_service import BadCaseService


class _FakeObs:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def model_dump(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _FakeObservationsApi:
    def __init__(self, data: list[Any]) -> None:
        self._data = data
        self.last_kwargs: dict[str, Any] = {}

    def get_many(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return type("Resp", (), {"data": self._data})()


class _FakeLangfuse:
    def __init__(self, data: list[Any]) -> None:
        self.observations = _FakeObservationsApi(data)
        self.api = type("Api", (), {"observations": self.observations})()


def test_build_dataset_payload_from_last_generation() -> None:
    gen = _FakeObs(
        id="obs-gen-2",
        type="GENERATION",
        start_time="2026-01-02T00:00:00Z",
        metadata={"agent_mode": 1},
        input={
            "messages": [
                {"role": "system", "content": "instructions"},
                {
                    "role": "user",
                    "content": "<user_message><query>什么是小镇婆罗门</query></user_message>",
                },
                {"role": "tool", "content": "tool result"},
            ],
            "tools": [{"name": "tavily_web_search"}],
        },
        output={"content": "小镇婆罗门是…"},
    )
    older = _FakeObs(
        id="obs-gen-1",
        type="GENERATION",
        start_time="2026-01-01T00:00:00Z",
        input={"messages": [{"role": "user", "content": "old"}]},
        output="old answer",
    )
    langfuse = _FakeLangfuse([gen, older])
    item = BadCaseItemDb(
        id="bad-1",
        source="low_score",
        message_id="msg-1",
        conversation_id="conv-1",
        user_id="user-1",
        query="截断 query",
        answer="截断 answer",
        judge_scores={
            "correctness": 3,
            "completeness": 2,
            "notes": "缺关键要点",
        },
        trace_id="trace-abc",
    )

    payload = BadCaseService._build_dataset_item_payload(item, langfuse)

    assert payload["source_trace_id"] == "trace-abc"
    assert payload["source_observation_id"] == "obs-gen-2"
    assert payload["expected_output"] == "小镇婆罗门是…"
    assert "tools" not in payload["input"]
    messages = payload["input"]["messages"]
    assert messages[0]["role"] == "system"
    assert "小镇婆罗门" in messages[1]["content"]
    assert messages[2]["role"] == "tool"

    meta = payload["metadata"]
    assert meta["source"] == "prod_trace"
    assert meta["user_id"] == "user-1"
    assert meta["version"] == "v1.0"
    assert meta["trace_id"] == "trace-abc"
    assert meta["agent_mode"] == 1
    assert meta["session_id"] == "conv-1"
    assert meta["bad_case_id"] == "bad-1"
    assert meta["bad_case_source"] == "low_score"
    assert "annotation" not in meta
    assert meta["judge_scores"]["correctness"] == 3
    assert meta["judge_scores"]["completeness"] == 2


def test_build_dataset_payload_falls_back_without_generation() -> None:
    langfuse = _FakeLangfuse([])
    item = BadCaseItemDb(
        id="bad-2",
        source="thumb_down",
        message_id="msg-2",
        conversation_id="conv-2",
        user_id="user-2",
        query="fallback query",
        answer="fallback answer",
        judge_scores=None,
        trace_id="trace-xyz",
    )

    payload = BadCaseService._build_dataset_item_payload(item, langfuse)

    assert payload["source_observation_id"] is None
    assert payload["expected_output"] == "fallback answer"
    assert payload["input"]["messages"] == [
        {"role": "user", "content": "fallback query"}
    ]
    assert payload["metadata"]["source"] == "prod_trace"
    assert payload["metadata"]["agent_mode"] == 0
    assert "annotation" not in payload["metadata"]
    assert payload["metadata"]["judge_scores"] is None


def test_add_to_dataset_calls_create_with_generation_payload(
    monkeypatch: Any,
) -> None:
    gen = _FakeObs(
        id="obs-1",
        type="GENERATION",
        start_time="2026-01-02T00:00:00Z",
        metadata={"agent_mode": 0},
        input={
            "messages": [
                {"role": "user", "content": "<query>q</query>"},
            ]
        },
        output="answer text",
    )
    fake_lf = _FakeLangfuse([gen])
    fake_lf.create_dataset_item = MagicMock()  # type: ignore[method-assign]
    fake_lf.create_dataset = MagicMock()  # type: ignore[method-assign]

    item = BadCaseItemDb(
        id="bad-3",
        source="low_score",
        query="q",
        answer="a",
        judge_scores={"correctness": 2, "completeness": 2, "notes": "n"},
        trace_id="t-1",
        conversation_id="c-1",
        user_id="u-1",
    )
    db = MagicMock()
    db.get.return_value = item

    monkeypatch.setattr(
        "app.services.eval.bad_case_service.get_langfuse",
        lambda: fake_lf,
    )
    monkeypatch.setattr(
        "app.services.eval.bad_case_service.ensure_dataset",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.eval.bad_case_service.settings.langfuse.bad_case_dataset_name",
        "chat-agent-bad-cases",
    )

    service = BadCaseService(db)
    result = service.add_to_dataset("bad-3")

    assert result.status == "resolved"
    assert result.resolution == "added_to_dataset"
    fake_lf.create_dataset_item.assert_called_once()
    kwargs = fake_lf.create_dataset_item.call_args.kwargs
    assert kwargs["id"] == "bad-3"
    assert kwargs["source_observation_id"] == "obs-1"
    assert kwargs["expected_output"] == "answer text"
    assert kwargs["metadata"]["source"] == "prod_trace"
