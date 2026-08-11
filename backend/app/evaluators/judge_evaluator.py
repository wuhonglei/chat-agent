"""裁判模型：调用 LLM 对回答质量打分。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.utils.logger import logger

LLMCaller = Callable[[list[dict[str, str]]], Awaitable[str]]

REFERENCE_MAX_CHARS = 12_000
ANSWER_MAX_CHARS = 4_000

# 与离线 scripts SYSTEM_STEP2 对齐：有参考资料时以参考资料为事实依据
JUDGE_SYSTEM_NO_GOLD = """你是一个回答质量评估器。根据用户问题、参考资料、模型回答，打两个分。

## 重要规则

1. 如果输入中包含【参考资料/工具返回内容】，这些内容是从知识库、搜索引擎、用户附件中获取的真实数据。模型回答是基于这些参考资料生成的。评分时必须以参考资料为事实依据，不要用你自身的知识判断事实性。
2. 如果参考资料中确认了某个信息（如日期、金额、名称），模型回答中包含该信息就是正确的，不是虚构。
3. 只有当模型回答中的信息既不在参考资料中，也无法从参考资料推导出来时，才能判定为「虚构」。
4. **重要**：逐字核对专有名词，不得基于相似性推断。例如「深圳大学图书馆北馆」和「深圳图书馆北馆」是不同场所，地址不同。
5. 无参考资料时，以常识和逻辑判断正确性；完整性按是否充分回答用户问题判断。

## 评分标准

correctness_score（准确性，1-5）：回答中说的内容是否正确
  5=完全正确 4=基本正确有小瑕疵 3=部分正确有明显错误 2=大部分错误 1=完全错误
  注意：有参考资料时，以参考资料为准判断正确性；无参考资料时，以常识和逻辑判断。

completeness_score（完整性，1-5）：回答是否覆盖了问题应有的关键信息
  5=覆盖率>=90% 4=覆盖率>=70% 3=覆盖率>=50% 2=覆盖率<50% 1=几乎未覆盖

输出 JSON：
{"correctness_score": N, "completeness_score": N, "notes": "扣分原因简述"}"""


JUDGE_SYSTEM_WITH_GOLD = """你是一个回答质量评估器。根据用户问题、标准要点、模型回答，打两个分。

## 重要规则

1. 如果输入中包含【参考资料/工具返回内容】，这些内容是从知识库、搜索引擎、用户附件中获取的真实数据。模型回答是基于这些参考资料生成的。评分时必须以参考资料为事实依据，不要用你自身的知识判断事实性。
2. 如果参考资料中确认了某个信息（如日期、金额、名称），模型回答中包含该信息就是正确的，不是虚构。
3. 只有当模型回答中的信息既不在参考资料中，也无法从参考资料推导出来时，才能判定为「虚构」。
4. **重要**：逐字核对专有名词，不得基于相似性推断。例如「深圳大学图书馆北馆」和「深圳图书馆北馆」是不同场所，地址不同。

## 评分标准

correctness_score（准确性，1-5）：回答中说的内容是否正确
  5=完全正确 4=基本正确有小瑕疵 3=部分正确有明显错误 2=大部分错误 1=完全错误

completeness_score（完整性，1-5）：回答是否覆盖了标准要点
  5=覆盖率>=90% 4=覆盖率>=70% 3=覆盖率>=50% 2=覆盖率<50% 1=几乎未覆盖

输出 JSON：
{"correctness_score": N, "completeness_score": N, "notes": "扣分原因简述"}"""


def build_judge_user_prompt(
    *,
    query: str,
    answer: str,
    reference_contexts: str = "",
    ground_truth: str = "",
) -> str:
    """拼装裁判 user prompt（形状对齐 offline build_judge_input）。"""
    sections = [f"【用户问题】{query}"]
    if ground_truth.strip():
        sections.append(f"【标准要点】\n{ground_truth.strip()}")
    if reference_contexts.strip():
        sections.append(f"【参考资料/工具返回内容】\n{reference_contexts.strip()}")
    sections.append(f"【模型回答】\n{answer}")
    return "\n\n".join(sections)


@dataclass
class JudgeResult:
    """裁判评分结果"""

    correctness: int = 0
    completeness: int = 0
    notes: str = ""
    context_sources: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    success: bool = True
    error: str | None = None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
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
    notes = data.get("notes") or data.get("comment") or ""

    return JudgeResult(
        correctness=correctness,
        completeness=completeness,
        notes=str(notes),
    )


async def call_judge_model(
    *,
    query: str,
    answer: str,
    retrieved_contexts: str = "",
    reference_contexts: str = "",
    ground_truth: str = "",
    llm_caller: LLMCaller,
    context_sources: dict[str, Any] | None = None,
) -> JudgeResult:
    """调用裁判模型打分。

    Args:
        query: 用户问题（可含 memories 拼接）
        answer: 模型回答
        retrieved_contexts: 参考资料（兼容旧参数名）
        reference_contexts: 参考资料（优先于 retrieved_contexts）
        ground_truth: 标准答案要点（可选，有则走 WITH_GOLD）
        llm_caller: LLM 调用函数
        context_sources: 上下文来源标记，原样挂到 JudgeResult
    """
    refs = (reference_contexts or retrieved_contexts or "").strip()
    answer_text = answer[:ANSWER_MAX_CHARS]
    refs_text = refs[:REFERENCE_MAX_CHARS] if refs else ""

    if ground_truth.strip():
        system = JUDGE_SYSTEM_WITH_GOLD
        user_prompt = build_judge_user_prompt(
            query=query,
            answer=answer_text,
            reference_contexts=refs_text,
            ground_truth=ground_truth.strip(),
        )
    else:
        system = JUDGE_SYSTEM_NO_GOLD
        user_prompt = build_judge_user_prompt(
            query=query,
            answer=answer_text,
            reference_contexts=refs_text or "（无参考资料）",
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = await llm_caller(messages)
        result = _parse_judge_response(raw)
        result.raw_response = raw
        if context_sources:
            result.context_sources = dict(context_sources)
        return result
    except Exception as exc:
        logger.warning(
            "Judge model call failed",
            error=exc,
            error_type=type(exc).__name__,
        )
        return JudgeResult(
            success=False,
            error=str(exc),
            context_sources=dict(context_sources or {}),
        )
