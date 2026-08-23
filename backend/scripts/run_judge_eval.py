"""从 Langfuse Dataset 运行 LLM-as-a-Judge 评估（v4 experiment runner）。

流程：
  1. 通过 dataset.run_experiment() 获取 dataset items
  2. task: 直接返回 expected_output（评估已有回答）
  3. evaluator: 用 SYSTEM_STEP2 裁判 prompt 打分（correctness + completeness）
  4. 实验结果自动写入 Langfuse Experiments，支持 UI 对比

用法:
    uv run python scripts/run_judge_eval.py [--dry-run] [--limit N] [--run-name NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx
from langfuse import Evaluation, Langfuse
from langfuse.experiment import ExperimentItem

# ── 配置（优先读环境变量，fallback 为默认值） ────────────────────
DATASET_NAME = "chat-agent-eval"

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k:
                os.environ[_k] = _v

DASHSCOPE_API_BASE = os.environ.get(
    "DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DASHSCOPE_MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen3.8-max")

LF_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LF_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
LF_HOST = os.environ.get("LANGFUSE_HOST", "https://langfuse.wuhonglei.cn")

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # 秒，指数退避


# ── 裁判系统提示词 ──────────────────────────────────────────────
SYSTEM_STEP2 = """你是一个回答质量评估器。根据用户问题、标准要点（含权重）、模型回答，打两个分。

## 重要规则

1. 如果输入中包含【参考资料/工具返回内容】，这些内容是从知识库、搜索引擎、用户附件中获取的真实数据。模型回答是基于这些参考资料生成的。评分时必须以参考资料为事实依据，不要用你自身的知识判断事实性。
2. 如果参考资料中确认了某个信息（如日期、金额、名称），模型回答中包含该信息就是正确的，不是虚构。
3. 只有当模型回答中的信息既不在参考资料中，也无法从参考资料推导出来时，才能判定为「虚构」。
4. **重要**：逐字核对专有名词，不得基于相似性推断。例如「深圳大学图书馆北馆」和「深圳图书馆北馆」是不同场所，地址不同。

## 评分标准

correctness_score（准确性，1-5）：回答中说的内容是否正确
  5=完全正确 4=基本正确有小瑕疵 3=部分正确有明显错误 2=大部分错误 1=完全错误
  注意：有参考资料时，以参考资料为准判断正确性；无参考资料时，以常识和逻辑判断。

completeness_score（完整性，1-5）：回答是否覆盖了标准要点（按权重计算）
  评分规则：
  - 标注为【核心】的要点权重更高，未覆盖核心要点扣分更重
  - 标注为【补充】的要点权重较低，未覆盖不严重扣分
  - 简单事实性问题：只要覆盖了核心要点，即使补充要点未覆盖，完整性也应给 4-5 分
  - 5=核心要点全部覆盖 4=核心要点全部覆盖、补充要点部分覆盖 3=核心要点部分覆盖 2=核心要点大部分未覆盖 1=核心要点几乎未覆盖

scene_tag（场景标签）：qa=知识问答 rag=检索回答 tool=工具调用 chat=闲聊创意

输出 JSON：
{"correctness_score": N, "completeness_score": N, "scene_tag": "...", "notes": "扣分原因简述"}"""


def get_api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "未找到 DASHSCOPE_API_KEY，请设置环境变量或写入 backend/.env"
        )
    return key


# ── 消息提取与 XML 拼接 ─────────────────────────────────────────


def extract_messages_for_judge(item_input: dict) -> tuple[str, str]:
    """从 input.messages 中提取 user 内容和 tool 上下文。"""
    messages = item_input.get("messages", [])
    if not messages:
        return "", ""

    query = ""
    context_parts: list[str] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user" and content:
            query = content.strip()
        elif role == "tool":
            if content and content.strip():
                context_parts.append(content.strip())

    context_xml = _build_context_xml(context_parts)
    return query, context_xml


def _build_context_xml(tool_contents: list[str]) -> str:
    if not tool_contents:
        return ""
    parts = ["<参考资料>"]
    for i, content in enumerate(tool_contents, 1):
        parts.append(f"<来源_{i}>\n{content}\n</来源_{i}>")
    parts.append("</参考资料>")
    return "\n".join(parts)


def build_judge_input(
    query: str, context_xml: str, ground_truth_points: list, model_answer: str
) -> str:
    sections = [f"【用户问题】{query}"]
    if ground_truth_points:
        formatted_points = []
        for p in ground_truth_points:
            if isinstance(p, dict):
                label = "【核心】" if p.get("weight") == "core" else "【补充】"
                formatted_points.append(f"- {label}{p['text']}")
            else:
                # 兼容旧格式 list[str]
                formatted_points.append(f"- {p}")
        sections.append("【标准要点】\n" + "\n".join(formatted_points))
    if context_xml:
        sections.append(f"【参考资料/工具返回内容】\n{context_xml}")
    sections.append(f"【模型回答】\n{model_answer}")
    return "\n\n".join(sections)


# ── LLM 调用 ────────────────────────────────────────────────────


def call_judge(api_key: str, user_prompt: str) -> dict:
    """调用裁判模型，返回评分 dict。自动重试 transient 错误。"""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{DASHSCOPE_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DASHSCOPE_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_STEP2},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 1000,
                    "enable_thinking": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]

            try:
                if "{" in raw:
                    json_str = raw[raw.index("{") : raw.rindex("}") + 1]
                    return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
            return {"error": raw}

        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code < 500
                and exc.response.status_code != 429
            ):
                raise
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(
                    f"    [RETRY {attempt + 1}/{MAX_RETRIES}] {type(exc).__name__}, wait {wait}s..."
                )
                time.sleep(wait)

    return {"error": f"exhausted {MAX_RETRIES} retries: {last_exc}"}


# ── task & evaluator ────────────────────────────────────────────

_api_key: str | None = None
_judge_cache: dict[str, dict] = {}  # key: item id, value: judge result
_replay_context_queue: list[str] = []  # replay context 队列（task 存，evaluator 取）
_replay_judge_query_queue: list[str] = []  # replay judge query 队列


def push_replay_context(context_xml: str) -> None:
    """replay 模式：replay_task 存入当前 item 的真实 context。"""
    _replay_context_queue.append(context_xml)


def pop_replay_context() -> str | None:
    """replay 模式：evaluator 取出当前 item 的真实 context。"""
    if _replay_context_queue:
        return _replay_context_queue.pop(0)
    return None


def push_replay_judge_query(query: str) -> None:
    """replay 模式：存入拼接了 memories/attachments 的完整 query。"""
    _replay_judge_query_queue.append(query)


def pop_replay_judge_query() -> str | None:
    """replay 模式：evaluator 取出完整 query。"""
    if _replay_judge_query_queue:
        return _replay_judge_query_queue.pop(0)
    return None


def judge_task(*, item: ExperimentItem, **kwargs) -> str:
    """task: 直接返回 expected_output（我们评估的是已有的模型回答）。"""
    return item.expected_output or ""


def _get_judge_result(input_data, metadata, output) -> dict:
    """调用裁判模型，带缓存避免同一 item 重复调用。"""
    item_input = input_data if isinstance(input_data, dict) else {}
    annotation = (metadata or {}).get("annotation", {})
    ground_truth_points = annotation.get("ground_truth_points", [])

    query, context_xml = extract_messages_for_judge(item_input)
    if not query:
        return {"error": "no query found"}

    # replay 模式：优先使用 replay 的真实 query 和 context
    replay_q = pop_replay_judge_query()
    if replay_q:
        query = replay_q
    replay_ctx = pop_replay_context()
    if replay_ctx:
        context_xml = replay_ctx

    cache_key = f"{query[:100]}|{output[:100]}"
    if cache_key in _judge_cache:
        return _judge_cache[cache_key]

    judge_input = build_judge_input(
        query, context_xml, ground_truth_points, output or ""
    )
    result = call_judge(_api_key, judge_input)
    _judge_cache[cache_key] = result
    return result


def correctness_evaluator(
    *, input, output, expected_output, metadata, **kwargs
) -> Evaluation:
    """evaluator: 返回 correctness 分数。"""
    result = _get_judge_result(input, metadata, output)
    if "error" in result:
        return Evaluation(
            name="correctness", value=0, comment=f"judge error: {result['error'][:100]}"
        )
    return Evaluation(
        name="correctness",
        value=result.get("correctness_score", 0),
        comment=result.get("notes", ""),
    )


def completeness_evaluator(
    *, input, output, expected_output, metadata, **kwargs
) -> Evaluation:
    """evaluator: 返回 completeness 分数。"""
    result = _get_judge_result(input, metadata, output)
    if "error" in result:
        return Evaluation(
            name="completeness",
            value=0,
            comment=f"judge error: {result['error'][:100]}",
        )
    scene_tag = result.get("scene_tag", "")
    return Evaluation(
        name="completeness",
        value=result.get("completeness_score", 0),
        comment=f"scene={scene_tag}",
    )


# ── 主流程 ──────────────────────────────────────────────────────


def run(
    dry_run: bool = False, limit: int | None = None, run_name: str | None = None
) -> None:
    global _api_key

    client = Langfuse(
        public_key=LF_PUBLIC_KEY,
        secret_key=LF_SECRET_KEY,
        host=LF_HOST,
    )

    if not run_name:
        run_name = time.strftime("judge-%Y%m%d-%H%M%S")
    print(f"Run name: {run_name}")

    if dry_run:
        # dry-run: 只拉 items 不调裁判
        dataset = client.get_dataset(DATASET_NAME)
        items = dataset.items
        if limit:
            items = items[:limit]
        print(f"Dataset items: {len(items)}")
        for i, item in enumerate(items):
            item_input = item.input if isinstance(item.input, dict) else {}
            query, _ = extract_messages_for_judge(item_input)
            print(f"  [{i + 1}] query={query[:80]}...")
        return

    _api_key = get_api_key()

    # 获取 dataset
    dataset = client.get_dataset(DATASET_NAME)
    total = len(dataset.items)
    print(f"Dataset items: {total}")

    # 限制条数：用 langfuse.run_experiment() + local data
    if limit:
        items = dataset.items[:limit]
        result = client.run_experiment(
            name=DATASET_NAME,
            run_name=run_name,
            description=f"LLM-as-a-Judge eval ({len(items)}/{total} items, model={DASHSCOPE_MODEL})",
            data=items,
            task=judge_task,
            evaluators=[correctness_evaluator, completeness_evaluator],
            max_concurrency=3,
            metadata={
                "judge_model": DASHSCOPE_MODEL,
                "dataset": DATASET_NAME,
                "total_items": str(len(items)),
            },
        )
    else:
        result = dataset.run_experiment(
            name=run_name,
            description=f"LLM-as-a-Judge eval ({total} items, model={DASHSCOPE_MODEL})",
            task=judge_task,
            evaluators=[correctness_evaluator, completeness_evaluator],
            max_concurrency=3,
            metadata={
                "judge_model": DASHSCOPE_MODEL,
                "dataset": DATASET_NAME,
                "total_items": str(total),
            },
        )

    # 汇总
    print(f"\n{'=' * 60}")
    print(result.format())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LLM-as-a-Judge on Langfuse Dataset"
    )
    parser.add_argument("--dry-run", action="store_true", help="只构建输入，不调用裁判")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条")
    parser.add_argument(
        "--run-name", type=str, default=None, help="Experiment run 名称"
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, run_name=args.run_name)


if __name__ == "__main__":
    main()
