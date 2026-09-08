"""问答前记忆检索规则闸门：判断当前问题是否需要检索用户记忆。

纯规则、无 LLM。未命中 SKIP/MEMORY 时默认检索（宁可多查不漏查）。
"""

from __future__ import annotations

import re
from typing import Literal

Reason = Literal["short", "skip", "memory", "default"]

# 不需要记忆的意图模式
_SKIP_PATTERN_SOURCES = (
    r"什么是|what is|how does|explain|定义|区别",
    r"帮我写|write a|implement|debug|fix this|报错|error",
    r"翻译|translate|convert|格式化",
    r"^(好的|ok|thanks|谢谢|嗯|yes|no|对|是的)[\s。!.]*$",
    r"计算|calculate|算一下|\d+\s*[+\-*/]\s*\d+",
)

# 需要记忆的意图模式
_MEMORY_PATTERN_SOURCES = (
    r"我之前|上次|之前说过|remember|previously|last time",
    r"推荐|recommend|建议.*我|for me",
    r"继续|continue|接着|then what",
    r"我的|my |我喜欢|I prefer|I like",
)

_SKIP_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _SKIP_PATTERN_SOURCES)
_MEMORY_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _MEMORY_PATTERN_SOURCES)


def _matches_any(query: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(query) for pattern in patterns)


def classify_memory_need(query: str) -> tuple[bool, Reason]:
    """返回 (是否需要检索, 命中原因)。"""
    query_lower = query.lower().strip()

    if len(query_lower) < 5:
        return False, "short"

    hit_skip = _matches_any(query_lower, _SKIP_PATTERNS)
    hit_memory = _matches_any(query_lower, _MEMORY_PATTERNS)

    if hit_memory:
        return True, "memory"

    if hit_skip:
        return False, "skip"

    return True, "default"


def needs_memory(query: str) -> bool:
    """判断当前用户问题是否需要检索个人记忆。"""
    needed, _ = classify_memory_need(query)
    return needed
