"""sampler 分层采样单元测试。"""

from __future__ import annotations

from app.evaluators.sampler import (
    RiskLevel,
    classify_risk,
    detect_special_signals,
    is_effective_answer,
    stratified_sample,
)


def _trace(
    *,
    tid: str = "t1",
    output: str = (
        "这是一段足够长的有效回答内容，用于通过闲聊预筛阈值并进入候选池。"
        "再补充更多说明文字，确保总长度明确超过五十个字符阈值。"
    ),
    scores: list[dict] | None = None,
    metadata: dict | None = None,
    latency: float = 1.0,
    called_tools: list[str] | None = None,
) -> dict:
    meta = dict(metadata or {})
    if called_tools is not None:
        meta["called_tools"] = called_tools
    return {
        "id": tid,
        "output": output,
        "input": "用户问题",
        "latency": latency,
        "scores": scores
        or [
            {"name": "valid_answer", "value": True},
            {"name": "tool_call_count", "value": 0},
        ],
        "metadata": meta,
    }


def test_classify_risk_high_by_called_tools() -> None:
    t = _trace(called_tools=["shell_exec"], scores=[
        {"name": "valid_answer", "value": True},
        {"name": "tool_call_count", "value": 1},
    ])
    assert classify_risk(t) == RiskLevel.HIGH


def test_classify_risk_medium_by_search_tool() -> None:
    t = _trace(called_tools=["tavily_web_search"], scores=[
        {"name": "valid_answer", "value": True},
        {"name": "tool_call_count", "value": 1},
    ])
    assert classify_risk(t) == RiskLevel.MEDIUM


def test_classify_risk_medium_when_tool_count_without_names() -> None:
    t = _trace(
        scores=[
            {"name": "valid_answer", "value": True},
            {"name": "tool_call_count", "value": 2},
        ]
    )
    assert classify_risk(t) == RiskLevel.MEDIUM


def test_classify_risk_low_no_tools() -> None:
    t = _trace()
    assert classify_risk(t) == RiskLevel.LOW


def test_is_effective_answer_rejects_invalid() -> None:
    t = _trace(
        scores=[
            {"name": "valid_answer", "value": False},
            {"name": "tool_call_count", "value": 0},
        ]
    )
    assert is_effective_answer(t) is False


def test_is_effective_answer_rejects_short_chat() -> None:
    t = _trace(output="你好呀")
    assert is_effective_answer(t) is False


def test_detect_special_thumb_down_follow_up_latency() -> None:
    t = _trace(
        tid="t-follow",
        metadata={"assistant_message_id": "msg-1"},
        latency=5,
    )
    assert detect_special_signals(
        t, thumb_down_message_ids={"msg-1"}
    )
    assert detect_special_signals(t, follow_up_trace_ids={"t-follow"})
    assert detect_special_signals(_trace(latency=45.0))


def test_stratified_sample_special_and_rates() -> None:
    traces = []
    # 1 special via thumb_down
    traces.append(
        _trace(
            tid="special",
            metadata={"assistant_message_id": "m-down"},
            called_tools=[],
        )
    )
    # 10 high risk
    for i in range(10):
        traces.append(
            _trace(
                tid=f"high-{i}",
                called_tools=["shell_exec"],
                scores=[
                    {"name": "valid_answer", "value": True},
                    {"name": "tool_call_count", "value": 1},
                ],
            )
        )
    # 20 medium
    for i in range(20):
        traces.append(
            _trace(
                tid=f"med-{i}",
                called_tools=["tavily_web_search"],
                scores=[
                    {"name": "valid_answer", "value": True},
                    {"name": "tool_call_count", "value": 1},
                ],
            )
        )
    # 20 low
    for i in range(20):
        traces.append(_trace(tid=f"low-{i}"))

    result = stratified_sample(
        traces,
        thumb_down_message_ids={"m-down"},
        seed=1,
    )
    assert result.breakdown["special"] == 1
    # 10 * 0.4 = 4
    assert result.breakdown["high"] == 4
    # 20 * 0.15 = 3
    assert result.breakdown["medium"] == 3
    # 20 * 0.05 = 1
    assert result.breakdown["low"] == 1
    assert len(result.traces) == 1 + 4 + 3 + 1
