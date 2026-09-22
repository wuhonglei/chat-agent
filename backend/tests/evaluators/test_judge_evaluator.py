"""judge_evaluator 解析与调用单元测试。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from app.evaluators.judge_evaluator import (
    EVAL_JUDGE_OBSERVATION_NAME,
    JudgeResult,
    _parse_judge_response,
    build_judge_user_prompt,
    call_judge_model,
)


def test_parse_plain_json() -> None:
    raw = '{"correctness_score": 4, "completeness_score": 3, "notes": "缺一点"}'
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
        dialogue_history="<dialogue_history>hist</dialogue_history>",
    )
    assert "【用户问题】q" in prompt
    assert "【历史对话（仅供理解上下文，不作为事实依据）】" in prompt
    assert "<dialogue_history>hist</dialogue_history>" in prompt
    assert "【标准要点】" in prompt
    assert "【参考资料/工具返回内容】" in prompt
    assert "【模型回答】" in prompt
    # 历史段位于参考资料之前
    assert prompt.index("【历史对话") < prompt.index("【参考资料/工具返回内容】")


def test_build_judge_user_prompt_without_history_omits_section() -> None:
    prompt = build_judge_user_prompt(query="q", answer="a")
    assert "【历史对话" not in prompt


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
async def test_call_judge_model_with_images_builds_multimodal_content() -> None:
    captured: list[list[dict[str, Any]]] = []

    async def _caller(messages: list[dict[str, Any]]) -> str:
        captured.append(messages)
        return '{"correctness_score": 5, "completeness_score": 5, "notes": "对"}'

    result = await call_judge_model(
        query="这是什么",
        answer="一张户口簿照片",
        llm_caller=_caller,
        images=["data:image/jpeg;base64,IMG1", "data:image/png;base64,IMG2"],
    )
    assert result.success is True
    user_content = captured[0][1]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "text"
    assert "【用户图片】用户问题附带 2 张图片" in user_content[0]["text"]
    image_parts = [p for p in user_content if p["type"] == "image_url"]
    assert [p["image_url"]["url"] for p in image_parts] == [
        "data:image/jpeg;base64,IMG1",
        "data:image/png;base64,IMG2",
    ]


@pytest.mark.asyncio
async def test_call_judge_model_without_images_keeps_string_content() -> None:
    captured: list[list[dict[str, Any]]] = []

    async def _caller(messages: list[dict[str, Any]]) -> str:
        captured.append(messages)
        return '{"correctness_score": 4, "completeness_score": 4}'

    result = await call_judge_model(query="q", answer="a", llm_caller=_caller)
    assert result.success is True
    assert isinstance(captured[0][1]["content"], str)
    assert "【用户图片】" not in captured[0][1]["content"]


@pytest.mark.asyncio
async def test_call_judge_model_with_dialogue_history() -> None:
    captured: list[list[dict[str, Any]]] = []

    async def _caller(messages: list[dict[str, Any]]) -> str:
        captured.append(messages)
        return '{"correctness_score": 4, "completeness_score": 5, "notes": "ok"}'

    history = (
        "<dialogue_history>\n"
        '<hist_turn index="1" role="user">看看这张图</hist_turn>\n'
        '<hist_turn index="2" role="assistant">这是一张猫的照片</hist_turn>\n'
        "</dialogue_history>"
    )
    result = await call_judge_model(
        query="它是什么颜色",
        answer="橘色",
        llm_caller=_caller,
        dialogue_history=history,
    )
    assert result.success is True
    user = captured[0][1]["content"]
    assert isinstance(user, str)
    assert "【历史对话（仅供理解上下文，不作为事实依据）】" in user
    assert "这是一张猫的照片" in user
    system = captured[0][0]["content"]
    assert "不作为评判事实性的依据" in system


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


@pytest.mark.asyncio
async def test_call_judge_model_opens_eval_judge_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    updated: dict[str, Any] = {}

    class _FakeSpan:
        def update(self, **kwargs: Any) -> None:
            updated.update(kwargs)

    @contextmanager
    def _fake_span(name: str, **kwargs: Any) -> Any:
        captured["name"] = name
        captured["kwargs"] = kwargs
        yield _FakeSpan()

    monkeypatch.setattr(
        "app.evaluators.judge_evaluator.observation_span",
        _fake_span,
    )

    async def _caller(_messages: list[dict[str, str]]) -> str:
        return '{"correctness_score": 4, "completeness_score": 5, "notes": "ok"}'

    result = await call_judge_model(query="q", answer="a", llm_caller=_caller)

    assert result.success is True
    assert captured["name"] == EVAL_JUDGE_OBSERVATION_NAME
    assert captured["kwargs"]["as_type"] == "evaluator"
    assert captured["kwargs"]["trace_name"] == EVAL_JUDGE_OBSERVATION_NAME
    assert captured["kwargs"]["metadata"] == {"source": "eval_worker"}
    assert updated["output"]["correctness"] == 4
    assert updated["output"]["completeness"] == 5
