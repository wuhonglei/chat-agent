"""LLM 调用错误分类、重试退避与进程级熔断。"""

from __future__ import annotations

import threading
import time
from email.utils import parsedate_to_datetime
from typing import Any, Literal

from app.schemas.config import LLMReliabilityConfig
from app.utils.logger import logger

ErrorReason = Literal[
    "quota",
    "auth",
    "busy",
    "transient",
    "generic",
    "circuit_open",
]

_RETRIABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_BUSY_PATTERNS = (
    "server busy",
    "temporarily unavailable",
    "try again later",
    "please retry",
    "please try again",
    "overloaded",
    "high demand",
    "rate limit",
    "负载较高",
    "服务繁忙",
    "稍后重试",
    "请稍后重试",
)
_QUOTA_PATTERNS = (
    "insufficient_quota",
    "quota",
    "billing",
    "credit",
    "payment",
    "余额不足",
    "超出限额",
    "额度不足",
    "欠费",
)
_AUTH_PATTERNS = (
    "authentication",
    "unauthorized",
    "invalid api key",
    "invalid_api_key",
    "permission",
    "forbidden",
    "access denied",
    "无权",
    "未授权",
)
_TRANSIENT_EXCEPTION_NAMES = frozenset(
    {
        "APITimeoutError",
        "APIConnectionError",
        "InternalServerError",
        "ReadError",
        "RemoteProtocolError",
        "StreamChunkTimeoutError",
    }
)
_DETAIL_MAX_LEN = 500


class LLMCallError(Exception):
    """面向调用方的 LLM 失败异常；``str(exc)`` 为用户可读中文。"""

    def __init__(
        self,
        *,
        reason: ErrorReason,
        user_message: str,
        detail: str = "",
        status_code: int | None = None,
    ) -> None:
        self.reason = reason
        self.user_message = user_message
        self.detail = detail
        self.status_code = status_code
        super().__init__(user_message)

    def __str__(self) -> str:
        return self.user_message


class CircuitBreaker:
    """进程内 closed / open / half-open 熔断器（单探针）。"""

    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_sec: int,
        key: str = "",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.key = key
        self._lock = threading.Lock()
        self._failure_count = 0
        self._open_until = 0.0
        self._state = "closed"
        self._probe_in_flight = False

    def is_open(self) -> bool:
        """True = 熔断打开（快速失败），False = 允许请求（含 half-open 探针）。"""
        with self._lock:
            now = time.time()
            if self._state == "open":
                if now < self._open_until:
                    return True
                self._state = "half_open"
                self._probe_in_flight = False

            if self._state == "half_open":
                if self._probe_in_flight:
                    return True
                self._probe_in_flight = True
                return False

            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state != "closed" or self._failure_count > 0:
                logger.info(
                    "LLM circuit breaker reset (Closed)",
                    api_base=self.key or None,
                )
            self._failure_count = 0
            self._open_until = 0.0
            self._state = "closed"
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._open_until = time.time() + self.recovery_timeout_sec
                self._state = "open"
                self._probe_in_flight = False
                logger.error(
                    "LLM circuit breaker probe failed (Open)",
                    api_base=self.key or None,
                    recovery_timeout_sec=self.recovery_timeout_sec,
                )
                return

            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_until = time.time() + self.recovery_timeout_sec
                if self._state != "open":
                    self._state = "open"
                    self._probe_in_flight = False
                    logger.error(
                        "LLM circuit breaker tripped (Open)",
                        api_base=self.key or None,
                        failure_threshold=self.failure_threshold,
                        recovery_timeout_sec=self.recovery_timeout_sec,
                    )

    def release_probe(self) -> None:
        """取消/中断时释放 half-open 探针占用。"""
        with self._lock:
            if self._state == "half_open":
                self._probe_in_flight = False


_breakers_lock = threading.Lock()
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    api_base: str,
    config: LLMReliabilityConfig,
) -> CircuitBreaker:
    """按 api_base 获取进程级共享熔断器。"""
    with _breakers_lock:
        breaker = _breakers.get(api_base)
        if breaker is None:
            breaker = CircuitBreaker(
                failure_threshold=config.circuit_failure_threshold,
                recovery_timeout_sec=config.circuit_recovery_timeout_sec,
                key=api_base,
            )
            _breakers[api_base] = breaker
        else:
            breaker.failure_threshold = config.circuit_failure_threshold
            breaker.recovery_timeout_sec = config.circuit_recovery_timeout_sec
        return breaker


def reset_circuit_breakers_for_tests() -> None:
    """测试用：清空进程级熔断器表。"""
    with _breakers_lock:
        _breakers.clear()


def classify_error(exc: BaseException) -> tuple[bool, ErrorReason]:
    """返回 (是否可重试, 错误原因)。"""
    detail = extract_error_detail(exc)
    lowered = detail.lower()
    error_code = _extract_error_code(exc)
    status_code = extract_status_code(exc)

    if _matches_any(lowered, _QUOTA_PATTERNS) or _matches_any(
        str(error_code).lower(), _QUOTA_PATTERNS
    ):
        return False, "quota"
    if _matches_any(lowered, _AUTH_PATTERNS):
        return False, "auth"

    if type(exc).__name__ in _TRANSIENT_EXCEPTION_NAMES:
        return True, "transient"
    if status_code in _RETRIABLE_STATUS_CODES:
        return True, "transient"
    if _matches_any(lowered, _BUSY_PATTERNS):
        return True, "busy"

    return False, "generic"


def extract_retry_after_ms(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None

    raw = None
    header_name = ""
    for key in ("retry-after-ms", "Retry-After-Ms", "retry-after", "Retry-After"):
        header_name = key
        if hasattr(headers, "get"):
            raw = headers.get(key)
        if raw:
            break
    if not raw:
        return None

    try:
        multiplier = 1 if "ms" in header_name.lower() else 1000
        return max(0, int(float(str(raw)) * multiplier))
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(str(raw))
            delta = target.timestamp() - time.time()
            return max(0, int(delta * 1000))
        except (TypeError, ValueError, OverflowError):
            return None


def build_retry_delay_ms(
    attempt: int,
    exc: BaseException,
    *,
    base_delay_ms: int,
    cap_delay_ms: int,
) -> int:
    retry_after = extract_retry_after_ms(exc)
    if retry_after is not None:
        return retry_after
    backoff = int(base_delay_ms * (2 ** max(0, attempt - 1)))
    return min(backoff, cap_delay_ms)


def extract_error_detail(exc: BaseException) -> str:
    detail = str(exc).strip()
    if detail:
        return _truncate(detail)
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message.strip():
        return _truncate(message.strip())
    return type(exc).__name__


def extract_status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def user_message_for(reason: ErrorReason, exc: BaseException | None = None) -> str:
    if reason == "quota":
        return "账户配额不足或计费异常，请充值或检查账单后重试。"
    if reason == "auth":
        return "LLM 认证失败，请检查 API Key 或访问权限配置。"
    if reason == "circuit_open":
        return "LLM 服务连续失败，已暂时熔断保护，请稍后再试。"
    if reason in {"busy", "transient"}:
        return "LLM 服务暂时不可用，请稍后继续对话。"
    detail = extract_error_detail(exc) if exc is not None else ""
    if detail:
        return f"LLM 请求失败：{detail}"
    return "LLM 请求失败，请稍后重试。"


def build_llm_call_error(
    exc: BaseException,
    reason: ErrorReason,
) -> LLMCallError:
    return LLMCallError(
        reason=reason,
        user_message=user_message_for(reason, exc),
        detail=extract_error_detail(exc),
        status_code=extract_status_code(exc),
    )


def build_circuit_open_error() -> LLMCallError:
    return LLMCallError(
        reason="circuit_open",
        user_message=user_message_for("circuit_open"),
        detail="LLM circuit breaker is open",
    )


def counts_toward_circuit(reason: ErrorReason) -> bool:
    return reason in {"transient", "busy"}


def _matches_any(detail: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in detail for pattern in patterns)


def _extract_error_code(exc: BaseException) -> Any:
    for attr in ("code", "error_code"):
        value = getattr(exc, attr, None)
        if value not in (None, ""):
            return value

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            for key in ("code", "type"):
                value = error.get(key)
                if value not in (None, ""):
                    return value
    return None


def _truncate(detail: str) -> str:
    if len(detail) <= _DETAIL_MAX_LEN:
        return detail
    return detail[: _DETAIL_MAX_LEN - 3] + "..."
