"""将本地 eval_samples_annotated.json 的 case 同步到 Langfuse Dataset。

对每个 case：
  1. 用 trace_id 查询 Langfuse observations API
  2. 找到最后一条 name=OpenAI-generation 的 GENERATION observation
  3. 创建 dataset item，input={query, context}，关联 source_trace_id + source_observation_id

用法:
    uv run python scripts/sync_eval_to_langfuse_dataset.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from langfuse import Langfuse

DATASET_NAME = "chat-agent-eval"
EVAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples_annotated.json"
)

# 加载 .env（优先读环境变量，fallback 为 .env）
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

LF_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LF_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
LF_HOST = os.environ.get("LANGFUSE_HOST", "https://langfuse.wuhonglei.cn")


def make_langfuse_client() -> Langfuse:
    return Langfuse(
        public_key=LF_PUBLIC_KEY,
        secret_key=LF_SECRET_KEY,
        host=LF_HOST,
    )


def find_last_generation(client: Langfuse, trace_id: str) -> dict | None:
    """返回该 trace 下最后一条 OpenAI-generation observation 的 I/O，找不到返回 None。"""
    try:
        resp = client.api.observations.get_many(
            trace_id=trace_id,
            limit=50,
            fields="io",
        )
    except Exception as exc:
        print(f"    [WARN] observations API error for trace {trace_id[:20]}: {exc}")
        return None

    # fields='io' 下 name 为 None，只按 type=GENERATION 过滤
    # observations 按 start_time 降序排列，第一条就是最后一条
    gens = [o for o in resp.data if o.type == "GENERATION"]
    if not gens:
        return None

    last = gens[0]
    input_data = last.input
    # 移除 tools 字段，只保留 messages
    if isinstance(input_data, str):
        try:
            input_data = __import__("json").loads(input_data)
        except Exception:
            pass
    if isinstance(input_data, dict):
        input_data = {k: v for k, v in input_data.items() if k != "tools"}
    return {
        "id": last.id,
        "input": input_data,
        "output": last.output,
    }


def build_metadata(item: dict) -> dict:
    """从 eval JSON 构建 dataset item 的 metadata。"""
    return {
        "version": "v1.0",
        "source": "prod_trace",
        "trace_id": item.get("trace_id"),
        "session_id": item.get("session_id"),
        "user_id": item.get("user_id"),
        "agent_mode": item.get("agent_mode"),
        "annotation": item.get("annotation"),
    }


def run(dry_run: bool = False, limit: int | None = None) -> None:
    data: list[dict] = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    total = len(data)
    if limit:
        data = data[:limit]
    print(f"Eval samples: {total}, processing: {len(data)}")

    client = make_langfuse_client()

    stats = {"ok": 0, "no_gen": 0, "error": 0}

    for i, item in enumerate(data):
        trace_id: str = item["trace_id"]
        query_preview = item["query"][:60]
        print(
            f"\n[{i + 1}/{len(data)}] trace={trace_id[:20]}... query={query_preview}..."
        )

        # 1. 查找最后一条 OpenAI-generation（含 I/O）
        gen_info = find_last_generation(client, trace_id)
        if gen_info is None:
            print("    [SKIP] no OpenAI-generation found")
            stats["no_gen"] += 1
            continue
        obs_id = gen_info["id"]
        print(f"    last_gen_obs_id={obs_id}")

        if dry_run:
            print("    [DRY-RUN] would create dataset item")
            stats["ok"] += 1
            continue

        # 2. 创建 dataset item，使用 observation 的真实 I/O + eval JSON metadata
        try:
            result = client.api.dataset_items.create(
                dataset_name=DATASET_NAME,
                input=gen_info["input"],
                expected_output=gen_info["output"],
                metadata=build_metadata(item),
                source_trace_id=trace_id,
                source_observation_id=obs_id,
            )
            print(f"    [OK] dataset_item_id={result.id}")
            stats["ok"] += 1
        except Exception as exc:
            print(f"    [ERROR] create failed: {exc}")
            stats["error"] += 1

        # 简单限流：每 5 条暂停 0.5s，避免触发 rate limit
        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    print(f"\n{'=' * 60}")
    print(f"Done. OK={stats['ok']}, NoGen={stats['no_gen']}, Error={stats['error']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync eval samples to Langfuse Dataset"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只查找 observation，不创建 dataset item"
    )
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条")
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
