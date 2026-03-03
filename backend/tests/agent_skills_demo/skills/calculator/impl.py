"""Calculator Skill 实现"""

import ast
import operator
from typing import Any

from ..base import BaseSkill, SkillContext, SkillResult

# 允许的数学运算（安全子集）
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

_SAFE_FUNCS = {
    "sqrt": lambda x: x**0.5 if x >= 0 else None,
    "abs": abs,
    "sin": __import__("math").sin,
    "cos": __import__("math").cos,
    "tan": __import__("math").tan,
    "log": __import__("math").log,
}


def _eval_expr(node: ast.AST) -> float | None:
    """安全求值 AST 节点"""
    if isinstance(node, ast.Constant):
        return float(node.value) if isinstance(node.value, (int, float)) else None
    if isinstance(node, ast.BinOp):
        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        if left is None or right is None:
            return None
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            return None
        try:
            return float(op(left, right))  # type: ignore[operator]
        except ZeroDivisionError:
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _eval_expr(node.operand)
        return -val if val is not None else None
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            return None
        name = node.func.id
        if name not in _SAFE_FUNCS:
            return None
        if len(node.args) != 1:
            return None
        arg = _eval_expr(node.args[0])
        if arg is None:
            return None
        try:
            return float(_SAFE_FUNCS[name](arg))
        except (ValueError, TypeError):
            return None
    return None


class SkillImpl(BaseSkill):
    """计算器 Skill 实现"""

    async def execute(
        self,
        params: dict[str, Any],
        context: SkillContext | None = None,
    ) -> SkillResult:
        expression = params.get("expression", "")
        if not expression or not isinstance(expression, str):
            return SkillResult(
                success=False,
                error="缺少 expression 参数",
            )

        try:
            tree = ast.parse(expression, mode="eval")
            result = _eval_expr(tree.body)
            if result is None:
                return SkillResult(
                    success=False,
                    error="无法计算该表达式，可能包含不安全或不受支持的操作",
                )
            return SkillResult(success=True, data={"result": result})
        except SyntaxError as e:
            return SkillResult(success=False, error=f"表达式语法错误: {e}")
