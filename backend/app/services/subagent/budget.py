"""Reject goals that must not be delegated."""

from __future__ import annotations


def goal_rejection_reason(goal: str) -> str | None:
    """Reject empty goals and unexpanded TODO templates. None means the goal is usable."""
    if not goal or not goal.strip():
        return "goal 不能为空"
    if "TODO" in goal:
        return "goal 含未展开的 TODO 模板标记，请写成完整任务描述"
    return None
