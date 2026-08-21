"""Tests for LLM cache usage parsing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.utils import llm_usage as llm_usage_module
from app.utils.llm_usage import extract_cache_usage, log_llm_cache_usage


def test_extract_deepseek_cache_fields() -> None:
    usage = SimpleNamespace(
        prompt_tokens=1000,
        prompt_cache_hit_tokens=700,
        prompt_cache_miss_tokens=300,
    )
    result = extract_cache_usage(usage)
    assert result["cache_hit_tokens"] == 700
    assert result["cache_miss_tokens"] == 300
    assert result["prompt_tokens"] == 1000
    assert result["hit_ratio"] == 0.7


def test_extract_openai_cached_tokens() -> None:
    usage = {
        "prompt_tokens": 500,
        "prompt_tokens_details": {"cached_tokens": 200},
    }
    result = extract_cache_usage(usage)
    assert result["cache_hit_tokens"] == 200
    assert result["prompt_tokens"] == 500
    assert result["hit_ratio"] == 0.4


def test_extract_input_cached_tokens_compat() -> None:
    usage = {"prompt_tokens": 100, "input_cached_tokens": 40}
    result = extract_cache_usage(usage)
    assert result["cache_hit_tokens"] == 40
    assert result["hit_ratio"] == 0.4


def test_extract_empty_usage() -> None:
    result = extract_cache_usage(None)
    assert result["cache_hit_tokens"] is None
    assert result["prompt_tokens"] is None
    assert result["hit_ratio"] is None


def test_log_llm_cache_usage_skips_none(monkeypatch) -> None:
    mock_logger = MagicMock()
    monkeypatch.setattr(llm_usage_module, "logger", mock_logger)
    log_llm_cache_usage(None, model="m")
    mock_logger.info.assert_not_called()


def test_log_llm_cache_usage_emits(monkeypatch) -> None:
    mock_logger = MagicMock()
    monkeypatch.setattr(llm_usage_module, "logger", mock_logger)
    log_llm_cache_usage(
        {"prompt_tokens": 10, "prompt_cache_hit_tokens": 4},
        model="m",
        iteration=1,
    )
    mock_logger.info.assert_called_once()
    args, kwargs = mock_logger.info.call_args
    assert args[0] == "llm_cache_usage"
    assert kwargs["cache_hit_tokens"] == 4
    assert kwargs["model"] == "m"
    assert kwargs["iteration"] == 1
