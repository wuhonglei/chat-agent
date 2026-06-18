"""observability helper 单元测试（不依赖真实 Langfuse 客户端）。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core import observability


def test_observation_span_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability, "is_enabled", lambda: False)

    with observability.observation_span("memory-search", input={"q": "hi"}) as span:
        assert span is None


def test_observation_span_noop_when_client_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(observability, "is_enabled", lambda: True)
    monkeypatch.setattr(observability, "get_langfuse", lambda: None)

    with observability.observation_span("kb-rag-build") as span:
        assert span is None


def test_observation_span_yields_span_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, Any] = {}

    class _FakeSpan:
        def update(self, **kwargs: Any) -> None:
            started["update"] = kwargs

    class _FakeCM:
        def __enter__(self) -> _FakeSpan:
            return _FakeSpan()

        def __exit__(self, *args: Any) -> None:
            return None

    class _FakeClient:
        def start_as_current_observation(self, **kwargs: Any) -> _FakeCM:
            started["kwargs"] = kwargs
            return _FakeCM()

    monkeypatch.setattr(observability, "is_enabled", lambda: True)
    monkeypatch.setattr(observability, "get_langfuse", lambda: _FakeClient())

    with observability.observation_span(
        "embedding", as_type="span", input={"text_length": 3}
    ) as span:
        assert span is not None
        span.update(output={"dimension": 1024})

    assert started["kwargs"]["name"] == "embedding"
    assert started["kwargs"]["as_type"] == "span"
    assert started["kwargs"]["input"] == {"text_length": 3}
    assert started["update"] == {"output": {"dimension": 1024}}


def test_observation_span_noop_when_start_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        def start_as_current_observation(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    monkeypatch.setattr(observability, "is_enabled", lambda: True)
    monkeypatch.setattr(observability, "get_langfuse", lambda: _FakeClient())

    with observability.observation_span("memory-write") as span:
        assert span is None


def test_mark_observation_error_handles_none() -> None:
    # 不应抛异常
    observability.mark_observation_error(None, RuntimeError("x"))


def test_mark_observation_error_sets_level() -> None:
    captured: dict[str, Any] = {}

    class _FakeSpan:
        def update(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    observability.mark_observation_error(_FakeSpan(), ValueError("bad"))

    assert captured["level"] == "ERROR"
    assert captured["status_message"] == "ValueError"


def test_mark_observation_error_swallows_update_failure() -> None:
    class _FakeSpan:
        def update(self, **kwargs: Any) -> None:
            raise RuntimeError("update failed")

    # 不应冒泡
    observability.mark_observation_error(_FakeSpan(), ValueError("bad"))


def test_flush_langfuse_noop_when_client_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(observability, "get_langfuse", lambda: None)
    observability.flush_langfuse()


def test_flush_langfuse_calls_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    flushed: dict[str, bool] = {}

    class _FakeClient:
        def flush(self) -> None:
            flushed["called"] = True

    monkeypatch.setattr(observability, "get_langfuse", lambda: _FakeClient())
    observability.flush_langfuse()

    assert flushed["called"] is True
