"""judge_evaluator 解析与调用单元测试。"""

from __future__ import annotations

import pytest

from app.evaluators.judge_evaluator import (
    JudgeResult,
    _parse_judge_response,
    build_judge_user_prompt,
    call_judge_model,
)


def test_parse_plain_json() -> None:
    raw = (
        '{"correctness_score": 4, "completeness_score": 3, "notes": "缺一点"}'
    )
    result = _parse_judge_response(raw)
    assert result.success is True
    assert result.correctness == 4
    assert result.completeness == 3
    assert result.notes == "缺一点"


def test_parse_fenced_json_and_score_alias() -> None:
    raw = """```json
{"score": 5}
```"""
    result = _parse_judge_response(raw)
    assert result.success is True
    assert result.correctness == 5
    assert result.completeness == 5


def test_parse_invalid_json() -> None:
    result = _parse_judge_response("not json at all")
    assert result.success is False
    assert result.error


def test_build_judge_user_prompt_shape() -> None:
    prompt = build_judge_user_prompt(
        query="q",
        answer="a",
        reference_contexts="<参考资料>ctx</参考资料>",
        ground_truth="- point",
    )
    assert "【用户问题】q" in prompt
    assert "【标准要点】" in prompt
    assert "【参考资料/工具返回内容】" in prompt
    assert "【模型回答】" in prompt


@pytest.mark.asyncio
async def test_call_judge_model_no_gold_uses_reference_prompt() -> None:
    captured: list[list[dict[str, str]]] = []

    async def _caller(messages: list[dict[str, str]]) -> str:
        captured.append(messages)
        return '{"correctness_score": 4, "completeness_score": 4, "notes": "ok"}'

    result = await call_judge_model(
        query="q",
        answer="a",
        reference_contexts="ctx",
        llm_caller=_caller,
        context_sources={"last_generation": True},
    )
    assert result.success is True
    assert result.correctness == 4
    assert result.notes == "ok"
    assert result.context_sources["last_generation"] is True
    assert len(captured) == 1
    system = captured[0][0]["content"]
    user = captured[0][1]["content"]
    assert "参考资料为事实依据" in system
    assert "【参考资料/工具返回内容】" in user
    assert "ctx" in user


@pytest.mark.asyncio
async def test_call_judge_model_with_gold() -> None:
    captured: list[list[dict[str, str]]] = []

    async def _caller(messages: list[dict[str, str]]) -> str:
        captured.append(messages)
        return '{"correctness_score": 5, "completeness_score": 5}'

    result = await call_judge_model(
        query="q",
        answer="a",
        ground_truth="- 要点1",
        reference_contexts="ctx",
        llm_caller=_caller,
    )
    assert result.success is True
    user = captured[0][1]["content"]
    assert "【标准要点】" in user
    assert "要点1" in user


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


@pytest.mark.asyncio
async def test_retrieved_contexts_alias() -> None:
    async def _caller(messages: list[dict[str, str]]) -> str:
        assert "legacy-ctx" in messages[1]["content"]
        return '{"correctness_score": 3, "completeness_score": 3}'

    result = await call_judge_model(
        query="q",
        answer="a",
        retrieved_contexts="legacy-ctx",
        llm_caller=_caller,
    )
    assert result.success is True
