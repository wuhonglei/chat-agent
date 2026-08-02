"""从 Langfuse 线上 Trace 采样生成评估集 v1.0。

用法:
    uv run python scripts/sample_traces_for_eval.py

输出:
    data/eval_set/v1.0/eval_samples.json   — 采样结果（待标注）
    data/eval_set/v1.0/stats.json          — 采样统计
"""

import json
import subprocess
import random
from collections import Counter
from pathlib import Path

# ── Langfuse 配置 ──────────────────────────────────────────────
LANGFUSE_HOST = "https://langfuse.wuhonglei.cn"
LANGFUSE_PUBLIC_KEY = "pk-lf-26ef9e82-6509-46b4-a4e7-33b1e496d3ae"
LANGFUSE_SECRET_KEY = "sk-lf-fabdfda1-7803-4442-9908-065963106875"
AUTH = f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}"

# ── 采样参数 ────────────────────────────────────────────────────
TARGET_SAMPLE_SIZE = 150          # 目标采样条数
PAGE_SIZE = 50                    # API 每页条数
RANDOM_SEED = 42

# ── 输出目录 ────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_set" / "v1.0"


def fetch_all_traces() -> list[dict]:
    """分页拉取所有 traces。"""
    all_traces = []
    page = 1
    while True:
        result = subprocess.run(
            ["curl", "-s", "-u", AUTH,
             f"{LANGFUSE_HOST}/api/public/traces?limit={PAGE_SIZE}&page={page}",
             "--connect-timeout", "10", "--max-time", "20"],
            capture_output=True, text=True, timeout=25,
        )
        data = json.loads(result.stdout)
        traces = data.get("data", [])
        if not traces:
            break
        all_traces.extend(traces)
        total_pages = data.get("meta", {}).get("totalPages", 1)
        print(f"  Page {page}/{total_pages}: {len(traces)} traces")
        if page >= total_pages:
            break
        page += 1
    return all_traces


def classify_trace(t: dict) -> str:
    """将 trace 分类到采样桶。"""
    meta = t.get("metadata") or {}
    agent_mode = meta.get("agent_mode", 0)
    has_scores = bool(t.get("scores"))
    latency = t.get("latency", 0)

    if agent_mode == 1:
        return "agent_mode"           # Agent 工具调用
    if has_scores:
        return "already_scored"       # 已有评分
    if latency and latency > 50:
        return "high_latency"         # 高延迟（>50s）
    return "normal"                   # 普通问答


def stratified_sample(traces: list[dict], target: int) -> list[dict]:
    """分层采样：各桶按比例分配，确保覆盖所有场景。"""
    random.seed(RANDOM_SEED)

    # 分桶
    buckets: dict[str, list[dict]] = {}
    for t in traces:
        bucket = classify_trace(t)
        buckets.setdefault(bucket, []).append(t)

    print(f"\n  Buckets:")
    samples = []
    for name, items in sorted(buckets.items()):
        # 每个桶至少取 5 条，其余按比例
        proportion = len(items) / len(traces)
        alloc = max(5, round(target * proportion))
        alloc = min(alloc, len(items))  # 不超过桶容量
        sampled = random.sample(items, alloc)
        samples.extend(sampled)
        print(f"    {name}: {len(items)} total, {alloc} sampled")

    # 如果不够，从 normal 桶补齐
    if len(samples) < target:
        sampled_ids = {s["id"] for s in samples}
        remaining = [t for t in buckets.get("normal", []) if t["id"] not in sampled_ids]
        extra = min(target - len(samples), len(remaining))
        samples.extend(random.sample(remaining, extra))
        print(f"    normal (补充): +{extra}")

    random.shuffle(samples)
    return samples[:target]


def build_eval_item(trace: dict) -> dict | None:
    """将 trace 转换为评估集条目。无效 trace 返回 None。"""
    # 过滤无效 trace：无输出 / 输出为空
    output = trace.get("output")
    if not output or not str(output).strip():
        return None

    meta = trace.get("metadata") or {}
    return {
        "trace_id": trace["id"],
        "session_id": trace.get("sessionId"),
        "user_id": trace.get("userId"),
        "timestamp": trace.get("timestamp"),
        "query": trace.get("input", ""),
        "answer": str(output),
        "model_id": meta.get("model_id", "unknown"),
        "agent_mode": meta.get("agent_mode", 0),
        "latency_s": trace.get("latency"),
        "cost_usd": trace.get("totalCost"),
        "has_existing_scores": bool(trace.get("scores")),
        "langfuse_url": f"{LANGFUSE_HOST}{trace.get('htmlPath', '')}",
        # 以下字段待人工标注
        "annotation": {
            "ground_truth_points": [],   # 标准答案要点（待填）
            "scene_tag": "",             # 场景标签：rag / tool / chat / qa
            "correctness_score": None,   # 1-5
            "completeness_score": None,  # 1-5
            "notes": "",                 # 标注备注
        },
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Step 1: Fetching all traces from Langfuse...")
    all_traces = fetch_all_traces()
    print(f"  Total: {len(all_traces)} traces\n")

    print("Step 2: Stratified sampling...")
    sampled = stratified_sample(all_traces, TARGET_SAMPLE_SIZE)
    print(f"\n  Final sample size: {len(sampled)}")

    print("\nStep 3: Building eval items...")
    eval_items = [item for item in (build_eval_item(t) for t in sampled) if item is not None]

    # 统计
    stats = {
        "total_traces": len(all_traces),
        "sample_size": len(eval_items),
        "seed": RANDOM_SEED,
        "model_distribution": dict(Counter(e["model_id"] for e in eval_items)),
        "agent_mode_distribution": {
            "normal": sum(1 for e in eval_items if e["agent_mode"] == 0),
            "agent": sum(1 for e in eval_items if e["agent_mode"] == 1),
        },
        "latency_stats": {},
        "cost_stats": {},
    }
    latencies = sorted([e["latency_s"] for e in eval_items if e["latency_s"]])
    if latencies:
        n = len(latencies)
        stats["latency_stats"] = {
            "min": round(min(latencies), 1),
            "p50": round(latencies[n // 2], 1),
            "p90": round(latencies[int(n * 0.9)], 1),
            "max": round(max(latencies), 1),
        }
    costs = sorted([e["cost_usd"] for e in eval_items if e["cost_usd"]])
    if costs:
        n = len(costs)
        stats["cost_stats"] = {
            "avg": round(sum(costs) / n, 4),
            "p50": round(costs[n // 2], 4),
            "max": round(max(costs), 4),
        }

    # 写入文件
    eval_path = OUTPUT_DIR / "eval_samples.json"
    eval_path.write_text(json.dumps(eval_items, ensure_ascii=False, indent=2))
    print(f"\n  Eval samples: {eval_path}")

    stats_path = OUTPUT_DIR / "stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"  Stats: {stats_path}")

    print(f"\nDone! {len(eval_items)} samples ready for annotation.")
    print(f"Next: open eval_samples.json, fill in 'annotation' fields for each item.")


if __name__ == "__main__":
    main()
