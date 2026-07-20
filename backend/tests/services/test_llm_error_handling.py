"""Tests for LLM error classification, retry, and circuit breaker."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from app.schemas.config import LLMConfig, LLMReliabilityConfig
from app.services.base_service.llm_error_handling import (
    CircuitBreaker,
    LLMCallError,
    build_retry_delay_ms,
    classify_error,
    extract_retry_after_ms,
    get_circuit_breaker,
    reset_circuit_breakers_for_tests,
    user_message_for,
)
from app.services.base_service.llm_service import LLMService


def _httpx_response(
    status_code: int = 429,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return httpx.Response(
        status_code,
        headers=headers or {},
        json=json_body or {"error": {"message": "rate limited"}},
        request=request,
    )


def _rate_limit(
    message: str = "Rate limit exceeded",
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> RateLimitError:
    return RateLimitError(
        message,
        response=_httpx_response(429, headers=headers, json_body=body),
        body=body or {"error": {"message": message}},
    )


def _status_error(
    status_code: int,
    message: str,
    *,
    body: dict[str, Any] | None = None,
) -> APIStatusError:
    return APIStatusError(
        message,
        response=_httpx_response(status_code, json_body=body),
        body=body or {"error": {"message": message}},
    )


def _connection_error(message: str = "Connection error.") -> APIConnectionError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return APIConnectionError(message=message, request=request)


@pytest.fixture(autouse=True)
def _clear_breakers() -> None:
    reset_circuit_breakers_for_tests()
    yield
    reset_circuit_breakers_for_tests()


def test_classify_rate_limit_retriable() -> None:
    retriable, reason = classify_error(_rate_limit())
    assert retriable is True
    assert reason == "transient"


def test_classify_503_retriable() -> None:
    retriable, reason = classify_error(_status_error(503, "Service Unavailable"))
    assert retriable is True
    assert reason == "transient"


def test_classify_connection_error_retriable() -> None:
    retriable, reason = classify_error(_connection_error())
    assert retriable is True
    assert reason == "transient"


def test_classify_quota_not_retriable() -> None:
    exc = _status_error(
        429,
        "You exceeded your current quota",
        body={"error": {"code": "insufficient_quota", "message": "余额不足"}},
    )
    retriable, reason = classify_error(exc)
    assert retriable is False
    assert reason == "quota"


def test_classify_auth_not_retriable() -> None:
    exc = AuthenticationError(
        "Invalid API key",
        response=_httpx_response(401),
        body={"error": {"message": "invalid_api_key"}},
    )
    retriable, reason = classify_error(exc)
    assert retriable is False
    assert reason == "auth"


def test_classify_busy_patterns() -> None:
    exc = _status_error(400, "服务繁忙，请稍后重试")
    retriable, reason = classify_error(exc)
    assert retriable is True
    assert reason == "busy"


def test_extract_retry_after_seconds() -> None:
    exc = _rate_limit(headers={"Retry-After": "2"})
    assert extract_retry_after_ms(exc) == 2000


def test_extract_retry_after_ms_header() -> None:
    exc = _rate_limit(headers={"Retry-After-Ms": "1500"})
    assert extract_retry_after_ms(exc) == 1500


def test_build_retry_delay_backoff_and_cap() -> None:
    exc = _connection_error()
    assert build_retry_delay_ms(1, exc, base_delay_ms=1000, cap_delay_ms=8000) == 1000
    assert build_retry_delay_ms(2, exc, base_delay_ms=1000, cap_delay_ms=8000) == 2000
    assert build_retry_delay_ms(4, exc, base_delay_ms=1000, cap_delay_ms=8000) == 8000


def test_build_retry_delay_prefers_retry_after() -> None:
    exc = _rate_limit(headers={"Retry-After": "3"})
    assert build_retry_delay_ms(1, exc, base_delay_ms=1000, cap_delay_ms=8000) == 3000


def test_user_message_chinese() -> None:
    assert "配额" in user_message_for("quota")
    assert "认证" in user_message_for("auth")
    assert "熔断" in user_message_for("circuit_open")
    assert "暂时不可用" in user_message_for("transient")


def test_circuit_breaker_trips_and_recovers() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_sec=30,
        key="https://api.example.com",
    )
    assert breaker.is_open() is False
    breaker.record_failure()
    assert breaker.is_open() is False
    breaker.record_failure()
    assert breaker.is_open() is True

    # Force half-open by backdating open_until
    breaker._open_until = 0.0  # noqa: SLF001
    assert breaker.is_open() is False  # probe allowed
    assert breaker.is_open() is True  # second concurrent probe blocked

    breaker.record_success()
    assert breaker.is_open() is False


def test_circuit_breaker_probe_failure_reopens() -> None:
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_sec=30,
        key="https://api.example.com",
    )
    breaker.record_failure()
    assert breaker.is_open() is True
    breaker._open_until = 0.0  # noqa: SLF001
    assert breaker.is_open() is False  # enter half-open + take probe
    breaker.record_failure()
    assert breaker.is_open() is True


def test_get_circuit_breaker_shared_by_api_base() -> None:
    config = LLMReliabilityConfig(circuit_failure_threshold=3)
    a = get_circuit_breaker("https://a.example.com", config)
    b = get_circuit_breaker("https://a.example.com", config)
    c = get_circuit_breaker("https://b.example.com", config)
    assert a is b
    assert a is not c


def _llm_service() -> LLMService:
    return LLMService(
        LLMConfig(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            model_name="test-model",
            context_limit=8192,
        )
    )


@pytest.mark.asyncio
async def test_call_llm_api_retries_then_succeeds() -> None:
    service = _llm_service()
    completion = MagicMock(name="completion")
    create = AsyncMock(
        side_effect=[
            _rate_limit(),
            _rate_limit(),
            completion,
        ]
    )
    service._client.chat.completions.create = create  # noqa: SLF001

    reliability = LLMReliabilityConfig(
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_cap_delay_ms=1,
    )
    with (
        patch("app.services.base_service.llm_service.settings") as settings_mock,
        patch(
            "app.services.base_service.llm_service.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        settings_mock.llm_reliability = reliability
        result = await service.call_llm_api(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )

    assert result is completion
    assert create.await_count == 3


@pytest.mark.asyncio
async def test_call_llm_api_non_retriable_single_attempt() -> None:
    service = _llm_service()
    auth_exc = AuthenticationError(
        "Invalid API key",
        response=_httpx_response(401),
        body={"error": {"message": "invalid_api_key"}},
    )
    create = AsyncMock(side_effect=auth_exc)
    service._client.chat.completions.create = create  # noqa: SLF001

    reliability = LLMReliabilityConfig(retry_max_attempts=3, retry_base_delay_ms=1)
    with patch("app.services.base_service.llm_service.settings") as settings_mock:
        settings_mock.llm_reliability = reliability
        with pytest.raises(LLMCallError) as exc_info:
            await service.call_llm_api(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                stream=False,
            )

    assert create.await_count == 1
    assert exc_info.value.reason == "auth"
    assert "认证" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_llm_api_circuit_open_skips_request() -> None:
    service = _llm_service()
    create = AsyncMock(return_value=MagicMock())
    service._client.chat.completions.create = create  # noqa: SLF001

    reliability = LLMReliabilityConfig(
        retry_max_attempts=3,
        circuit_failure_threshold=1,
        circuit_recovery_timeout_sec=60,
    )
    breaker = get_circuit_breaker(service.model_config.api_base, reliability)
    breaker.record_failure()

    with patch("app.services.base_service.llm_service.settings") as settings_mock:
        settings_mock.llm_reliability = reliability
        with pytest.raises(LLMCallError) as exc_info:
            await service.call_llm_api(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                stream=False,
            )

    assert create.await_count == 0
    assert exc_info.value.reason == "circuit_open"
    assert "熔断" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_llm_api_exhausted_retries_raises_friendly_error() -> None:
    service = _llm_service()
    create = AsyncMock(side_effect=_connection_error("upstream down"))
    service._client.chat.completions.create = create  # noqa: SLF001

    reliability = LLMReliabilityConfig(
        retry_max_attempts=2,
        retry_base_delay_ms=1,
        retry_cap_delay_ms=1,
    )
    with (
        patch("app.services.base_service.llm_service.settings") as settings_mock,
        patch(
            "app.services.base_service.llm_service.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        settings_mock.llm_reliability = reliability
        with pytest.raises(LLMCallError) as exc_info:
            await service.call_llm_api(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                stream=False,
            )

    assert create.await_count == 2
    assert exc_info.value.reason == "transient"
    assert "暂时不可用" in str(exc_info.value)
