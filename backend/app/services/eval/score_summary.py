"""构建评估运行的 score_summary（基于裁判成功样本）。"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from app.evaluators.judge_evaluator import JudgeResult
from app.evaluators.sampler import (
    classify_risk,
    detect_special_signals,
)

SCORE_SUMMARY_VERSION = 1
TIERS = ("special", "high", "medium", "low")
SCORE_BUCKETS = ("1", "2", "3", "4", "5")


def _round4(value: float) -> float:
    return round(value, 4)


def _avg(values: list[int | float]) -> float | None:
    if not values:
        return None
    return _round4(sum(values) / len(values))


def _median_int(values: list[int]) -> int | None:
    if not values:
        return None
    return int(median(values))


def _empty_hist() -> dict[str, int]:
    return dict.fromkeys(SCORE_BUCKETS, 0)


def _clamp_score(score: int) -> str:
    return str(min(5, max(1, int(score))))


def _resolve_tier(
    trace: dict[str, Any],
    *,
    follow_up_trace_ids: set[str],
    thumb_down_message_ids: set[str],
    high_latency_threshold_s: float,
) -> str:
    if detect_special_signals(
        trace,
        follow_up_trace_ids=follow_up_trace_ids,
        thumb_down_message_ids=thumb_down_message_ids,
        high_latency_threshold_s=high_latency_threshold_s,
    ):
        return "special"
    return classify_risk(trace).value


def build_score_summary(
    results: list[tuple[dict[str, Any], JudgeResult]],
    *,
    threshold_correctness: int,
    threshold_completeness: int,
    follow_up_trace_ids: set[str] | None = None,
    thumb_down_message_ids: set[str] | None = None,
    high_latency_threshold_s: float = 30.0,
) -> dict[str, Any]:
    """汇总裁判成功样本的得分分布与低分统计。

    低分判定（与当前入队语义对齐，双阈值快照）：
    correctness < threshold_correctness OR completeness < threshold_completeness
    当前配置仍为单一阈值时，两侧传入相同值即可。
    """
    follow_ups = follow_up_trace_ids or set()
    thumb_downs = thumb_down_message_ids or set()

    correctness_scores: list[int] = []
    completeness_scores: list[int] = []
    min_scores: list[int] = []
    hist_correctness = _empty_hist()
    hist_completeness = _empty_hist()

    tier_correctness: dict[str, list[int]] = defaultdict(list)
    tier_completeness: dict[str, list[int]] = defaultdict(list)

    low_count = 0
    bottleneck = {"correctness": 0, "completeness": 0, "both": 0}
    low_by_tier = dict.fromkeys(TIERS, 0)

    for trace, result in results:
        if not result.success:
            continue

        c = int(result.correctness)
        p = int(result.completeness)
        correctness_scores.append(c)
        completeness_scores.append(p)
        min_scores.append(min(c, p))
        hist_correctness[_clamp_score(c)] += 1
        hist_completeness[_clamp_score(p)] += 1

        tier = _resolve_tier(
            trace,
            follow_up_trace_ids=follow_ups,
            thumb_down_message_ids=thumb_downs,
            high_latency_threshold_s=high_latency_threshold_s,
        )
        if tier not in TIERS:
            tier = "low"
        tier_correctness[tier].append(c)
        tier_completeness[tier].append(p)

        c_low = c < threshold_correctness
        p_low = p < threshold_completeness
        if c_low or p_low:
            low_count += 1
            low_by_tier[tier] += 1
            if c_low and p_low:
                bottleneck["both"] += 1
            elif c_low:
                bottleneck["correctness"] += 1
            else:
                bottleneck["completeness"] += 1

    n = len(correctness_scores)
    low_rate = _round4(low_count / n) if n else 0.0

    by_tier: dict[str, Any] = {}
    for tier in TIERS:
        cs = tier_correctness.get(tier, [])
        ps = tier_completeness.get(tier, [])
        tier_n = len(cs)
        tier_low = low_by_tier[tier]
        by_tier[tier] = {
            "n": tier_n,
            "avg_correctness": _avg(cs),
            "avg_completeness": _avg(ps),
            "low_rate": _round4(tier_low / tier_n) if tier_n else 0.0,
        }

    return {
        "version": SCORE_SUMMARY_VERSION,
        "n": n,
        "threshold": {
            "correctness": threshold_correctness,
            "completeness": threshold_completeness,
        },
        "overall": {
            "avg_correctness": _avg(correctness_scores),
            "avg_completeness": _avg(completeness_scores),
            "avg_min": _avg(min_scores),
            "p50_correctness": _median_int(correctness_scores),
            "p50_completeness": _median_int(completeness_scores),
            "low_rate": low_rate,
        },
        "hist": {
            "correctness": hist_correctness,
            "completeness": hist_completeness,
        },
        "by_tier": by_tier,
        "low_score": {
            "count": low_count,
            "rate": low_rate,
            "by_bottleneck": bottleneck,
            "by_tier": low_by_tier,
        },
    }
