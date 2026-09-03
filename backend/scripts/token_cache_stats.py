#!/usr/bin/env python3
"""方案 A（llm_rendered_text 固化）缓存命中率基线/对比采集脚本。

数据源: Langfuse ClickHouse `events_full` 表（self-hosted, 134.175.182.235:18123）。
凭证从环境变量读取（勿硬编码）:

    export LF_CH_URL="http://134.175.182.235:18123/"
    export LF_CH_USER="clickhouse"
    export LF_CH_PASSWORD="***"
    export LF_PROJECT_ID="cmpwgw3qg0005t407qhqzomsg"   # dev; prod=cmpwh4pcg0002qn07mv4f20af

用法:
    # 基线采集（部署改造前，dev 环境，最近 N 天）
    python3 token_cache_stats.py baseline --since 7d --out ../../docs/token_cache/plan_a_baseline.json

    # 部署改造后同参数再跑一次
    python3 token_cache_stats.py baseline --since 1d --out ../../docs/token_cache/plan_a_after.json

    # 对比两份快照并生成 markdown 报告
    python3 token_cache_stats.py compare \
        --baseline ../../docs/token_cache/plan_a_baseline.json \
        --after ../../docs/token_cache/plan_a_after.json \
        --out ../../docs/token_cache/plan_a_llm_rendered_text_report.md

核心指标（方案 A 的直接证据）:
    - per-turn first-call cache%: 每个 trace（一个 chat-turn）的首次 GENERATION
      命中率，衡量跨 turn 前缀连续性。改造前 turn N 的增强版 user message 在
      turn N+1 回放成裸文本导致断裂；改造后应命中到上一 turn 结尾。
    - turn-position 曲线: 按 session 内 turn 序号聚合 first-call cache%，
      改造前的 U 型低谷（Turn2-3 ~53%）应被抬平。
    - cached 卡死检测: 同一 trace 内 cached 连续 N 次不增长且非零。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# flash 系列无前缀缓存，统计时排除（可覆盖）
DEFAULT_MODEL_FILTER = "qwen3.8-max"


def ch_query(sql: str) -> list[dict[str, Any]]:
    url = os.environ.get("LF_CH_URL", "http://134.175.182.235:18123/")
    user = os.environ.get("LF_CH_USER", "clickhouse")
    password = os.environ.get("LF_CH_PASSWORD", "")
    if not password:
        print("ERROR: 请先 export LF_CH_PASSWORD", file=sys.stderr)
        sys.exit(1)
    # ClickHouse HTTP: POST body 即原始 SQL，无需 urlencode
    req = urllib.request.Request(url, data=sql.encode())
    req.add_header("Authorization", "Basic " + _b64(f"{user}:{password}"))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        print(f"ClickHouse HTTP {exc.code}: {exc.read().decode()[:500]}", file=sys.stderr)
        sys.exit(1)
    rows: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line:
            continue
        # 查询端 FORMAT JSONEachRow，逐行解析
        rows.append(json.loads(line))
    return rows


def _b64(s: str) -> str:
    import base64

    return base64.b64encode(s.encode()).decode()


def _normalize_since(since: str) -> str:
    """'7d' -> '7 DAY'；ClickHouse 不接受 'INTERVAL 1d' 这种缩写。"""
    import re

    m = re.fullmatch(r"(\d+)\s*(d|h|m|w|y|M)", since.strip())
    units = {"d": "DAY", "h": "HOUR", "m": "MINUTE", "w": "WEEK", "y": "YEAR", "M": "MONTH"}
    if m:
        return f"{m.group(1)} {units[m.group(2)]}"
    return since


def fetch_generations(project_id: str, since: str, model_filter: str) -> list[dict[str, Any]]:
    """按 trace 聚合取回每个 GENERATION 的 usage 明细（JSONEachRow）。"""
    sql = f"""
SELECT
  trace_id,
  session_id,
  start_time,
  provided_model_name as model,
  provided_usage_details['input'] as input_tokens,
  provided_usage_details['input_cached_tokens'] as cached_tokens,
  provided_usage_details['output'] as output_tokens
FROM events_full
WHERE project_id = '{project_id}'
  AND type = 'GENERATION'
  AND provided_model_name LIKE '%{model_filter}%'
  AND start_time >= now() - INTERVAL {_normalize_since(since)}
ORDER BY trace_id, start_time
FORMAT JSONEachRow
"""
    return ch_query(sql)


def cache_pct(inp: Any, cached: Any) -> float | None:
    try:
        inp = float(inp or 0)
        cached = float(cached or 0)
    except (TypeError, ValueError):
        return None
    denom = inp + cached
    if denom <= 0:
        return None
    return cached / denom * 100.0


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_trace[r["trace_id"]].append(r)

    turns: list[dict[str, Any]] = []
    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for trace_id, gens in by_trace.items():
        gens.sort(key=lambda g: g["start_time"])
        first = gens[0]
        pct = cache_pct(first["input_tokens"], first["cached_tokens"])
        turn = {
            "trace_id": trace_id,
            "session_id": first["session_id"],
            "start_time": first["start_time"],
            "iterations": len(gens),
            "first_input": int(first["input_tokens"] or 0),
            "first_cached": int(first["cached_tokens"] or 0),
            "first_call_cache_pct": round(pct, 1) if pct is not None else None,
            "trace_cache_pct": _trace_level_pct(gens),
            "cached_stuck": _detect_cached_stuck(gens),
        }
        turns.append(turn)
        sessions[first["session_id"]].append(turn)

    # turn 序号（按 session 内 start_time 排序）
    by_position: dict[int, list[float]] = defaultdict(list)
    for _sid, ts in sessions.items():
        ts.sort(key=lambda t: t["start_time"])
        for idx, t in enumerate(ts, start=1):
            t["turn_position"] = idx
            if t["first_call_cache_pct"] is not None:
                by_position[idx].append(t["first_call_cache_pct"])

    position_curve = {
        str(pos): {
            "samples": len(vals),
            "avg_first_call_cache_pct": round(sum(vals) / len(vals), 1),
        }
        for pos, vals in sorted(by_position.items())
    }

    total_input = sum(int(g["input_tokens"] or 0) for g in rows)
    total_cached = sum(int(g["cached_tokens"] or 0) for g in rows)
    first_pcts = [t["first_call_cache_pct"] for t in turns if t["first_call_cache_pct"] is not None]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_generations": len(rows),
        "total_traces": len(turns),
        "total_sessions": len(sessions),
        "token_cache_rate": round(
            total_cached / (total_input + total_cached) * 100, 1
        )
        if (total_input + total_cached) > 0
        else None,
        "first_call_cache_pct_avg": round(sum(first_pcts) / len(first_pcts), 1)
        if first_pcts
        else None,
        "first_call_cache_pct_p50": _pct(first_pcts, 50),
        "turn_position_curve": position_curve,
        "cached_stuck_traces": [t["trace_id"] for t in turns if t["cached_stuck"]],
        "turns": turns,
    }


def _trace_level_pct(gens: list[dict[str, Any]]) -> float | None:
    inp = sum(int(g["input_tokens"] or 0) for g in gens)
    cached = sum(int(g["cached_tokens"] or 0) for g in gens)
    if inp + cached <= 0:
        return None
    return round(cached / (inp + cached) * 100, 1)


def _detect_cached_stuck(gens: list[dict[str, Any]], min_gens: int = 3) -> bool:
    """cached 非零但连续 >=3 次 generation 不增长 → 前缀被破坏的典型模式。"""
    if len(gens) < min_gens:
        return False
    cached_seq = [int(g["cached_tokens"] or 0) for g in gens]
    run = 1
    for i in range(1, len(cached_seq)):
        if cached_seq[i] != 0 and cached_seq[i] == cached_seq[i - 1]:
            run += 1
            if run >= min_gens:
                return True
        else:
            run = 1
    return False


def _pct(vals: list[float], p: int) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    k = max(0, min(len(s) - 1, round(len(s) * p / 100) - 1))
    return round(s[k], 1)


def cmd_baseline(args: argparse.Namespace) -> None:
    rows = fetch_generations(args.project_id, args.since, args.model)
    if not rows:
        print("没有查询到 GENERATION 数据，检查 project_id / since / model 过滤条件")
        sys.exit(1)
    result = analyze(rows)
    result["params"] = {
        "project_id": args.project_id,
        "since": args.since,
        "model_filter": args.model,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _print_summary(result, args.out)


def _print_summary(r: dict[str, Any], out: str) -> None:
    print(f"快照已保存: {out}")
    print(f"  generations={r['total_generations']} traces={r['total_traces']} sessions={r['total_sessions']}")
    print(f"  token 级缓存率: {r['token_cache_rate']}%")
    print(f"  跨 turn 首调 cache%: avg={r['first_call_cache_pct_avg']} p50={r['first_call_cache_pct_p50']}")
    print("  turn 位置曲线 (首调 cache%):")
    for pos, item in r["turn_position_curve"].items():
        print(f"    Turn{pos}: n={item['samples']} avg={item['avg_first_call_cache_pct']}%")
    stuck = r["cached_stuck_traces"]
    print(f"  cached 卡死 trace: {len(stuck)}" + (f" -> {stuck[:5]}" if stuck else ""))


def cmd_compare(args: argparse.Namespace) -> None:
    with open(args.baseline) as f:
        base = json.load(f)
    with open(args.after) as f:
        after = json.load(f)

    def bucket_counts(r: dict[str, Any]) -> dict[str, int]:
        counts = {"low(0-20)": 0, "mid(20-70)": 0, "high(>=70)": 0, "none": 0}
        for t in r["turns"]:
            v = t["first_call_cache_pct"]
            if v is None:
                counts["none"] += 1
            elif v < 20:
                counts["low(0-20)"] += 1
            elif v < 70:
                counts["mid(20-70)"] += 1
            else:
                counts["high(>=70)"] += 1
        return counts

    lines = [
        "# 方案 A（llm_rendered_text 固化）缓存命中率对比报告",
        "",
        f"> 基线快照: `{args.baseline}`（{base.get('generated_at', '')}）",
        f"> 优化后快照: `{args.after}`（{after.get('generated_at', '')}）",
        f"> 模型过滤: {base.get('params', {}).get('model_filter', DEFAULT_MODEL_FILTER)}",
        "",
        "## 1. 整体对比",
        "",
        "| 指标 | 基线 | 优化后 | 变化 |",
        "|------|------|--------|------|",
    ]

    def row(name: str, key: str, suffix: str = "") -> None:
        b, a = base.get(key), after.get(key)
        diff = f"{a - b:+.1f}pp" if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "—"
        lines.append(f"| {name} | {b}{suffix} | {a}{suffix} | {diff} |")

    row("token 级缓存率", "token_cache_rate", "%")
    row("跨 turn 首调 cache% avg", "first_call_cache_pct_avg", "%")
    row("跨 turn 首调 cache% P50", "first_call_cache_pct_p50", "%")

    lines += [
        "",
        "## 2. 首调命中率分布（方案 A 核心指标）",
        "",
        "| 区间 | 基线 | 优化后 |",
        "|------|------|--------|",
    ]
    bb, ab = bucket_counts(base), bucket_counts(after)
    for k in bb:
        lines.append(f"| {k} | {bb[k]} | {ab[k]} |")

    lines += [
        "",
        "## 3. Turn 位置曲线（U 型低谷是否抬平）",
        "",
        "| Turn 序号 | 基线 n | 基线 cache% | 优化后 n | 优化后 cache% |",
        "|------|------|--------|------|--------|",
    ]
    positions = sorted(
        set(base.get("turn_position_curve", {})) | set(after.get("turn_position_curve", {})),
        key=int,
    )
    for pos in positions:
        b = base.get("turn_position_curve", {}).get(pos, {})
        a = after.get("turn_position_curve", {}).get(pos, {})
        lines.append(
            f"| Turn{pos} | {b.get('samples', '—')} | {b.get('avg_first_call_cache_pct', '—')}% "
            f"| {a.get('samples', '—')} | {a.get('avg_first_call_cache_pct', '—')}% |"
        )

    lines += [
        "",
        "## 4. cached 卡死检测",
        "",
        f"- 基线: {len(base.get('cached_stuck_traces', []))} 个 trace"
        f"{' → ' + ', '.join(base['cached_stuck_traces'][:5]) if base.get('cached_stuck_traces') else ''}",
        f"- 优化后: {len(after.get('cached_stuck_traces', []))} 个 trace"
        f"{' → ' + ', '.join(after['cached_stuck_traces'][:5]) if after.get('cached_stuck_traces') else ''}",
        "",
        "## 5. 达标判定",
        "",
        "| 目标 | 阈值 | 结果 |",
        "|------|------|------|",
    ]

    def verdict(cond: bool) -> str:
        return "✅" if cond else "⚠️ 未达"

    low_bucket_improved = ab["low(0-20)"] <= bb["low(0-20)"]
    stuck_improved = len(after.get("cached_stuck_traces", [])) <= len(
        base.get("cached_stuck_traces", [])
    )
    first_avg_ok = isinstance(after.get("first_call_cache_pct_avg"), (int, float)) and (
        not isinstance(base.get("first_call_cache_pct_avg"), (int, float))
        or after["first_call_cache_pct_avg"] >= base["first_call_cache_pct_avg"]
    )
    lines.append(f"| 低命中区间不增加 | ≤ 基线 | {verdict(low_bucket_improved)} |")
    lines.append(f"| cached 卡死不增加 | ≤ 基线 | {verdict(stuck_improved)} |")
    lines.append(f"| 首调 avg 不下降 | ≥ 基线 | {verdict(first_avg_ok)} |")

    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"报告已生成: {args.out}")
    print("\n".join(lines[:24]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_base = sub.add_parser("baseline", help="采集快照")
    p_base.add_argument("--since", default="7d", help="如 7d / 1d / 12h")
    p_base.add_argument(
        "--project-id",
        default=os.environ.get("LF_PROJECT_ID", "cmpwgw3qg0005t407qhqzomsg"),
    )
    p_base.add_argument("--model", default=DEFAULT_MODEL_FILTER)
    p_base.add_argument("--out", required=True, help="输出 json 路径")
    p_base.set_defaults(func=cmd_baseline)

    p_cmp = sub.add_parser("compare", help="对比两份快照生成 markdown 报告")
    p_cmp.add_argument("--baseline", required=True)
    p_cmp.add_argument("--after", required=True)
    p_cmp.add_argument("--out", required=True)
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
