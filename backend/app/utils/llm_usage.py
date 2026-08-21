"""Parse LLM usage / prompt-cache fields from OpenAI-compatible responses."""

from __future__ import annotations

from typing import Any

from app.utils.logger import logger


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def extract_cache_usage(usage: Any) -> dict[str, int | float | None]:
    """从 completion/chunk ``usage`` 提取缓存命中相关字段。

    兼容：
    - DeepSeek: ``prompt_cache_hit_tokens`` / ``prompt_cache_miss_tokens``
    - OpenAI: ``prompt_tokens_details.cached_tokens``
    - 其它: ``input_cached_tokens``
    """
    if usage is None:
        return {
            "cache_hit_tokens": None,
            "cache_miss_tokens": None,
            "prompt_tokens": None,
            "hit_ratio": None,
        }

    prompt_tokens = _as_int(_get(usage, "prompt_tokens"))
    cache_hit = _as_int(_get(usage, "prompt_cache_hit_tokens"))
    cache_miss = _as_int(_get(usage, "prompt_cache_miss_tokens"))

    if cache_hit is None:
        cache_hit = _as_int(_get(usage, "input_cached_tokens"))

    if cache_hit is None:
        details = _get(usage, "prompt_tokens_details")
        cache_hit = _as_int(_get(details, "cached_tokens"))

    hit_ratio: float | None = None
    if cache_hit is not None and prompt_tokens is not None and prompt_tokens > 0:
        hit_ratio = cache_hit / prompt_tokens

    return {
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "prompt_tokens": prompt_tokens,
        "hit_ratio": hit_ratio,
    }


def log_llm_cache_usage(usage: Any, **context: Any) -> None:
    """解析并打印 ``llm_cache_usage``；``usage`` 为空则跳过。"""
    if usage is None:
        return
    cache_usage = extract_cache_usage(usage)
    logger.info(
        "llm_cache_usage",
        cache_hit_tokens=cache_usage["cache_hit_tokens"],
        cache_miss_tokens=cache_usage["cache_miss_tokens"],
        prompt_tokens=cache_usage["prompt_tokens"],
        hit_ratio=cache_usage["hit_ratio"],
        **context,
    )
