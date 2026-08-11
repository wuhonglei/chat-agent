"""score_summary 构建单元测试。"""

from __future__ import annotations

from app.evaluators.judge_evaluator import JudgeResult
from app.services.eval.score_summary import build_score_summary


def _trace(*, trace_id: str = "t1", tools: list[str] | None = None) -> dict:
    return {
        "id": trace_id,
        "latency": 1.0,
        "metadata": {
            "called_tools": tools or [],
            "assistant_message_id": f"msg-{trace_id}",
        },
        "output": "足够长的有效回答内容用于通过规则预筛",
        "scores": [{"name": "valid_answer", "value": True}],
    }


def test_build_score_summary_basic() -> None:
    results = [
        (_trace(trace_id="a"), JudgeResult(correctness=5, completeness=4, success=True)),
        (_trace(trace_id="b"), JudgeResult(correctness=2, completeness=4, success=True)),
        (_trace(trace_id="c"), JudgeResult(correctness=2, completeness=2, success=True)),
        (_trace(trace_id="d"), JudgeResult(success=False, error="parse")),
    ]

    summary = build_score_summary(
        results,
        threshold_correctness=3,
        threshold_completeness=3,
    )

    assert summary["version"] == 1
    assert summary["n"] == 3
    assert summary["threshold"] == {"correctness": 3, "completeness": 3}
    assert summary["overall"]["avg_correctness"] == 3.0
    assert summary["overall"]["avg_completeness"] == _approx_avg([4, 4, 2])
    assert summary["overall"]["p50_correctness"] == 2
    assert summary["low_score"]["count"] == 2
    assert summary["low_score"]["by_bottleneck"] == {
        "correctness": 1,
        "completeness": 0,
        "both": 1,
    }
    assert summary["hist"]["correctness"]["5"] == 1
    assert summary["hist"]["correctness"]["2"] == 2


def _approx_avg(values: list[int]) -> float:
    return round(sum(values) / len(values), 4)


def test_build_score_summary_empty() -> None:
    summary = build_score_summary(
        [],
        threshold_correctness=3,
        threshold_completeness=3,
    )
    assert summary["n"] == 0
    assert summary["overall"]["avg_correctness"] is None
    assert summary["low_score"]["count"] == 0
    assert summary["low_score"]["rate"] == 0.0
    assert summary["by_tier"]["low"]["n"] == 0


def test_build_score_summary_special_tier() -> None:
    thumb_mid = "msg-special"
    trace = _trace(trace_id="special")
    trace["metadata"]["assistant_message_id"] = thumb_mid
    results = [
        (trace, JudgeResult(correctness=1, completeness=5, success=True)),
    ]
    summary = build_score_summary(
        results,
        threshold_correctness=3,
        threshold_completeness=3,
        thumb_down_message_ids={thumb_mid},
    )
    assert summary["by_tier"]["special"]["n"] == 1
    assert summary["low_score"]["by_tier"]["special"] == 1
