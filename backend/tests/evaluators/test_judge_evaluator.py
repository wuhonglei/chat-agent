"""judge_evaluator 解析与调用单元测试。"""

from __future__ import annotations

import pytest

from app.evaluators.judge_evaluator import (
    JudgeResult,
    _parse_judge_response,
    call_judge_model,
)


def test_parse_plain_json() -> None:
    raw = (
        '{"correctness_score": 4, "completeness_score": 3, '
        '"coverage": 0.6, "missing_points": ["a"]}'
    )
    result = _parse_judge_response(raw)
    assert result.success is True
    assert result.correctness == 4
    assert result.completeness == 3
    assert result.coverage == 0.6
    assert result.missing_points == ["a"]


def test_parse_fenced_json_and_score_alias() -> None:
    raw = """```json
{"score": 5, "missing_points": []}
```"""
    result = _parse_judge_response(raw)
    assert result.success is True
    assert result.correctness == 5
    assert result.completeness == 5


def test_parse_invalid_json() -> None:
    result = _parse_judge_response("not json at all")
    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_call_judge_model_success() -> None:
    async def _caller(_messages: list[dict[str, str]]) -> str:
        return '{"correctness_score": 4, "completeness_score": 4, "coverage": 0.8}'

    result = await call_judge_model(
        query="q",
        answer="a",
        retrieved_contexts="ctx",
        llm_caller=_caller,
    )
    assert result.success is True
    assert result.correctness == 4


@pytest.mark.asyncio
async def test_call_judge_model_failure() -> None:
    async def _caller(_messages: list[dict[str, str]]) -> str:
        raise RuntimeError("boom")

    result = await call_judge_model(
        query="q",
        answer="a",
        llm_caller=_caller,
    )
    assert result.success is False
    assert isinstance(result, JudgeResult)
    assert result.error == "boom"
