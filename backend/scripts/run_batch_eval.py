"""手动触发批量评估（调试用）。

用法:
    uv run python scripts/run_batch_eval.py [--hours 24] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.observability import init_langfuse
from app.services.eval.batch_eval_service import BatchEvalService
from eval_worker.main import judge_llm_caller


async def main() -> None:
    parser = argparse.ArgumentParser(description="手动触发分层采样批量评估")
    parser.add_argument(
        "--hours", type=int, default=None, help="拉取最近 N 小时的 Trace"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只采样不调裁判"
    )
    args = parser.parse_args()

    init_langfuse()
    service = BatchEvalService(llm_caller=judge_llm_caller)
    run_log = await service.run(
        run_type="manual",
        hours=args.hours,
        dry_run=args.dry_run,
    )

    print(f"\nRun ID: {run_log.id}")
    print(f"Status: {run_log.status}")
    print(f"Total traces: {run_log.total_traces}")
    print(f"After dedup: {run_log.after_dedup}")
    print(f"Candidate pool: {run_log.candidate_pool}")
    print(f"Sampled: {run_log.sampled_count}")
    print(f"Breakdown: {run_log.sample_breakdown}")
    print(f"Judge success: {run_log.judge_success}")
    print(f"Judge failed: {run_log.judge_failed}")
    print(f"Low scores: {run_log.low_score_count}")
    if run_log.error_message:
        print(f"Error: {run_log.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
