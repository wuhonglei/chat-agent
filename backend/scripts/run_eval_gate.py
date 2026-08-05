"""评估集 CI 回归门禁：跑评估集 → 算平均分 → 低于阈值 exit 1。

用法:
    # frozen 模式（默认，不需要服务运行）
    uv run python scripts/run_eval_gate.py

    # replay 模式（需要服务运行中 + 测试 token）
    uv run python scripts/run_eval_gate.py --replay --token <jwt>
    EVAL_GATE_TOKEN=eyJ... uv run python scripts/run_eval_gate.py --replay

    # 自定义阈值
    uv run python scripts/run_eval_gate.py --min-correctness 4.6 --min-completeness 4.4

    # 只跑评估，不检查阈值
    uv run python scripts/run_eval_gate.py --no-gate

    # 保存当前结果为 baseline
    uv run python scripts/run_eval_gate.py --save-baseline

    # 从 baseline 文件读取阈值
    uv run python scripts/run_eval_gate.py --baseline baseline.json

模式对比:
    frozen  — judge 对历史冻结回答打分（检测标注/裁判漂移）
    replay  — 对每条 query 重新调 API 生成回答，再 judge（检测 prompt/模型/架构变化）

输出:
    exit 0 = 门禁通过
    exit 1 = 门禁失败（分数低于阈值）
    exit 2 = 运行错误（API 失败等）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# 加载 .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

from langfuse import Langfuse  # noqa: E402
from langfuse.experiment import ExperimentItem  # noqa: E402

from scripts.run_judge_eval import (  # noqa: E402
    DATASET_NAME,
    completeness_evaluator,
    correctness_evaluator,
    judge_task,
    push_replay_context,
    push_replay_judge_query,
)

# ── 默认阈值（基于 baseline-v1-annot-fix 实验）──
DEFAULT_MIN_CORRECTNESS = 4.5
DEFAULT_MIN_COMPLETENESS = 4.3

# ── Replay 配置 ──
DEFAULT_BASE_URL = "http://localhost:8000"


def _make_replay_task(base_url: str, token: str):
    """创建 replay task 函数：调真实 API 重新生成回答。"""
    from pathlib import Path

    from scripts.eval_replay import (
        cleanup_conversation,
        create_conversation,
        extract_attachments_from_item,
        extract_context_from_blocks,
        extract_memories_from_item,
        extract_query_from_item,
        replay_query,
        upload_file,
    )

    # 附件目录
    attachments_dir = (
        Path(__file__).resolve().parent.parent / "data" / "eval_set" / "attachments"
    )

    def _find_local_file(filename: str) -> Path | None:
        """在附件目录中查找文件（模糊匹配，忽略空格/特殊字符）。"""
        if not attachments_dir.exists():
            return None
        # 精确匹配
        exact = attachments_dir / filename
        if exact.exists():
            return exact
        # 模糊匹配（去掉空格）
        normalized = filename.replace(" ", "")
        for f in attachments_dir.iterdir():
            if f.name.replace(" ", "") == normalized:
                return f
        return None

    def replay_task(*, item: ExperimentItem, **kwargs) -> str:
        """replay task: 调 API 重新生成回答（含附件上传）。"""
        item_input = item["input"] if isinstance(item["input"], dict) else {}  # type: ignore[index]
        query = extract_query_from_item(item_input)
        if not query:
            return "[ERROR] no query found"

        # 提取附件信息
        attachments = extract_attachments_from_item(item_input)
        memories = extract_memories_from_item(item_input)

        # 创建临时会话
        conv_id = create_conversation(
            base_url, token, title=f"eval-replay-{item['id']}"
        )  # type: ignore[index]
        if not conv_id:
            return "[ERROR] failed to create conversation"

        try:
            # 上传附件文件（如有）
            uploaded_files = []
            for att in attachments:
                local_path = _find_local_file(att["name"])
                if local_path:
                    upload_result = upload_file(
                        base_url, token, conv_id, str(local_path)
                    )
                    if upload_result:
                        uploaded_files.append(upload_result)
                    else:
                        return f"[ERROR] upload failed: {att['name']}"
                else:
                    return f"[ERROR] file not found: {att['name']}"

            # 调 API 重新生成
            answer, resp_blocks = replay_query(
                base_url,
                token,
                conv_id,
                query,
                attachments=attachments,
                uploaded_files=uploaded_files or None,
                memories=memories or None,
            )
            # 提取真实 context 和完整 query 推入裁判队列
            if resp_blocks:
                ctx_xml = extract_context_from_blocks(resp_blocks)
                if ctx_xml:
                    push_replay_context(ctx_xml)

            # 构造裁判用的完整 query（含 memories + attachments 信息）
            judge_query = _build_judge_query(query, memories, attachments)
            push_replay_judge_query(judge_query)

            return answer or "[ERROR] empty response"
        finally:
            # 清理临时会话
            cleanup_conversation(base_url, token, conv_id)


def _build_judge_query(
    query: str,
    memories: list[dict] | None,
    attachments: list[dict] | None,
) -> str:
    """构造裁判用的完整 query，拼接 memories 和 attachments 信息。"""
    parts = [query]
    if memories:
        mem_lines = "\n".join(f"- {m['memory']}" for m in memories)
        parts.append(f"<user_memories>\n{mem_lines}\n</user_memories>")
    if attachments:
        att_lines = "\n".join(f"- {a['name']} ({a['type']})" for a in attachments)
        parts.append(f"<attachments>\n{att_lines}\n</attachments>")
    return "\n\n".join(parts)

    return replay_task


def run_eval(
    *,
    replay: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    token: str = "",
) -> dict:
    """跑评估实验，返回 {run_name, avg_correctness, avg_completeness, item_count}。"""
    client = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ.get("LANGFUSE_HOST", "https://langfuse.wuhonglei.cn"),
    )

    mode = "replay" if replay else "frozen"
    run_name = time.strftime(f"eval-gate-{mode}-%Y%m%d-%H%M%S")
    print(f"Run: {run_name} (mode={mode})")

    dataset = client.get_dataset(DATASET_NAME)
    total = len(dataset.items)
    print(f"Dataset: {DATASET_NAME} ({total} items)")

    if replay:
        if not token:
            token = os.environ.get("EVAL_GATE_TOKEN", "")
        if not token:
            # 自动签发临时 token（读 .env 的 JWT 私钥）
            from scripts.eval_replay import generate_eval_token

            token = generate_eval_token()
            print("Auto-generated eval token (1h TTL)")
        task = _make_replay_task(base_url, token)
    else:
        task = judge_task

    result = dataset.run_experiment(
        name=run_name,
        description=f"CI eval gate ({total} items, mode={mode})",
        task=task,
        evaluators=[correctness_evaluator, completeness_evaluator],
        max_concurrency=3,
        metadata={"purpose": "ci_gate", "mode": mode, "dataset": DATASET_NAME},
    )

    # 计算平均分
    score_sums: dict[str, float] = defaultdict(float)
    score_counts: dict[str, int] = defaultdict(int)

    for item_result in result.item_results:
        for evaluation in item_result.evaluations:
            if isinstance(evaluation.value, (int, float)):
                score_sums[evaluation.name] += evaluation.value
                score_counts[evaluation.name] += 1

    avg_scores = {}
    for name in score_sums:
        if score_counts[name] > 0:
            avg_scores[name] = score_sums[name] / score_counts[name]

    return {
        "run_name": run_name,
        "mode": mode,
        "avg_correctness": avg_scores.get("correctness", 0),
        "avg_completeness": avg_scores.get("completeness", 0),
        "item_count": len(result.item_results),
        "avg_scores": avg_scores,
        "dataset_run_url": result.dataset_run_url,
    }


def check_gate(
    scores: dict,
    min_correctness: float,
    min_completeness: float,
) -> bool:
    """检查是否通过门禁。返回 True = 通过。"""
    c = scores["avg_correctness"]
    cp = scores["avg_completeness"]

    print(f"\n{'=' * 50}")
    print(f"  mode:         {scores.get('mode', 'unknown')}")
    print(f"  correctness:  {c:.3f}  (threshold: {min_correctness})")
    print(f"  completeness: {cp:.3f}  (threshold: {min_completeness})")
    print(f"{'=' * 50}")

    passed = True
    if c < min_correctness:
        print(f"  ❌ FAIL: correctness {c:.3f} < {min_correctness}")
        passed = False
    else:
        print(f"  ✅ PASS: correctness {c:.3f} >= {min_correctness}")

    if cp < min_completeness:
        print(f"  ❌ FAIL: completeness {cp:.3f} < {min_completeness}")
        passed = False
    else:
        print(f"  ✅ PASS: completeness {cp:.3f} >= {min_completeness}")

    return passed


def save_baseline(scores: dict, path: str) -> None:
    """保存当前分数为 baseline。"""
    baseline = {
        "run_name": scores["run_name"],
        "mode": scores.get("mode", "frozen"),
        "correctness": scores["avg_correctness"],
        "completeness": scores["avg_completeness"],
        "item_count": scores["item_count"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"Baseline saved to {path}")


def load_baseline(path: str) -> tuple[float, float]:
    """从 baseline 文件读取阈值（取 95% 作为阈值）。"""
    with open(path) as f:
        baseline = json.load(f)
    min_c = baseline["correctness"] * 0.95
    min_cp = baseline["completeness"] * 0.95
    print(f"Loaded baseline from {path} (mode={baseline.get('mode', 'unknown')}):")
    print(
        f"  correctness baseline={baseline['correctness']:.3f}, threshold={min_c:.3f}"
    )
    print(
        f"  completeness baseline={baseline['completeness']:.3f}, threshold={min_cp:.3f}"
    )
    return min_c, min_cp


def main() -> None:
    parser = argparse.ArgumentParser(description="评估集 CI 回归门禁")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="replay 模式：调真实 API 重新生成回答（需 --token）",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="JWT 测试 token（replay 模式必需，也可设 EVAL_GATE_TOKEN 环境变量）",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--min-correctness",
        type=float,
        default=None,
        help=f"correctness 最低阈值 (default: {DEFAULT_MIN_CORRECTNESS})",
    )
    parser.add_argument(
        "--min-completeness",
        type=float,
        default=None,
        help=f"completeness 最低阈值 (default: {DEFAULT_MIN_COMPLETENESS})",
    )
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="只跑评估，不检查阈值",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="保存当前结果为 baseline 文件",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="从 baseline 文件读取阈值",
    )
    args = parser.parse_args()

    # 确定阈值
    if args.baseline:
        min_c, min_cp = load_baseline(args.baseline)
    else:
        min_c = args.min_correctness or DEFAULT_MIN_CORRECTNESS
        min_cp = args.min_completeness or DEFAULT_MIN_COMPLETENESS

    # 跑评估
    try:
        scores = run_eval(
            replay=args.replay,
            base_url=args.base_url,
            token=args.token or "",
        )
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    # 输出结果
    print(f"\nDataset run: {scores.get('dataset_run_url', 'N/A')}")

    # 保存 baseline
    if args.save_baseline:
        baseline_path = (
            f"baseline_{scores.get('mode', 'frozen')}_{time.strftime('%Y%m%d')}.json"
        )
        save_baseline(scores, baseline_path)

    # 检查门禁
    if args.no_gate:
        print("\n--no-gate: skipping threshold check")
        sys.exit(0)

    passed = check_gate(scores, min_c, min_cp)
    if passed:
        print("\n✅ GATE PASSED")
        sys.exit(0)
    else:
        print("\n❌ GATE FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
