"""裁判模型：调用 LLM 对回答质量打分。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.utils.logger import logger

LLMCaller = Callable[[list[dict[str, str]]], Awaitable[str]]

# 裁判 Prompt（无标准答案版本：对比检索内容）
JUDGE_PROMPT_NO_GOLD = """你是一个回答完整性评估器。

【用户问题】{query}
【检索到的参考内容】{retrieved_contexts}
【模型回答】{answer}

请判断：
1. 参考内容中与问题相关的关键信息点有哪些？（逐条列出）
2. 模型回答覆盖了哪些？遗漏了哪些？
3. 覆盖率 = 已覆盖数 / 总相关要点数
4. 评分 1-5：
   - 5: 覆盖率 >= 90%
   - 4: 覆盖率 >= 70%
   - 3: 覆盖率 >= 50%
   - 2: 覆盖率 < 50%
   - 1: 几乎未利用检索内容

输出 JSON: {{"score": int, "correctness_score": int, "completeness_score": int, "coverage": float, "missing_points": ["..."]}}"""


# 裁判 Prompt（有标准答案版本：用于评估集回归）
JUDGE_PROMPT_WITH_GOLD = """你是一个回答质量评估器。

【用户问题】{query}
【标准答案要点】{ground_truth}
【模型回答】{answer}

请判断：
1. 标准答案的要点有哪些？（逐条列出）
2. 模型回答覆盖了哪些？遗漏了哪些？是否包含错误信息？
3. 评分 1-5：
   - 5: 完全正确且覆盖所有要点
   - 4: 覆盖大部分要点，无错误
   - 3: 覆盖一半要点，无重大错误
   - 2: 覆盖不足一半或有明显错误
   - 1: 几乎未回答或完全错误

输出 JSON: {{"score": int, "correctness_score": int, "completeness_score": int, "missing_points": ["..."]}}"""


@dataclass
class JudgeResult:
    """裁判评分结果"""

    correctness: int = 0
    completeness: int = 0
    coverage: float = 0.0
    missing_points: list[str] = field(default_factory=list)
    raw_response: str = ""
    success: bool = True
    error: str | None = None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_judge_response(raw: str) -> JudgeResult:
    """解析裁判模型的 JSON 输出。容错处理。"""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                return JudgeResult(success=False, error="Failed to parse JSON")
        else:
            return JudgeResult(success=False, error="No JSON found in response")

    if not isinstance(data, dict):
        return JudgeResult(success=False, error="Judge response is not an object")

    score = _as_int(data.get("score"), 0)
    correctness = _as_int(
        data.get("correctness_score", data.get("correctness", score)), score
    )
    completeness = _as_int(
        data.get("completeness_score", data.get("completeness", score)), score
    )
    missing = data.get("missing_points") or []
    if not isinstance(missing, list):
        missing = [str(missing)]

    return JudgeResult(
        correctness=correctness,
        completeness=completeness,
        coverage=_as_float(data.get("coverage"), 0.0),
        missing_points=[str(p) for p in missing],
    )


async def call_judge_model(
    *,
    query: str,
    answer: str,
    retrieved_contexts: str = "",
    ground_truth: str = "",
    llm_caller: LLMCaller,
) -> JudgeResult:
    """调用裁判模型打分。"""
    if ground_truth:
        prompt = JUDGE_PROMPT_WITH_GOLD.format(
            query=query,
            ground_truth=ground_truth,
            answer=answer[:2000],
        )
    else:
        prompt = JUDGE_PROMPT_NO_GOLD.format(
            query=query,
            retrieved_contexts=(retrieved_contexts or "（无检索内容）")[:3000],
            answer=answer[:2000],
        )

    messages = [
        {
            "role": "system",
            "content": "你是一个严格的回答质量评估器。只输出 JSON，不要输出其他内容。",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        raw = await llm_caller(messages)
        result = _parse_judge_response(raw)
        result.raw_response = raw
        return result
    except Exception as exc:
        logger.warning(
            "Judge model call failed",
            error=exc,
            error_type=type(exc).__name__,
        )
        return JudgeResult(success=False, error=str(exc))
