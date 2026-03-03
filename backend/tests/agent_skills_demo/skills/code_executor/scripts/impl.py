"""Code Executor Skill 实现（使用 RestrictedPython 沙箱）"""

import io
import sys
from typing import Any

from ...base import BaseSkill, SkillContext, SkillResult

try:
    from restrictedpython import compile_restricted_exec
    from restrictedpython.guards import full_write_guard, guarded_iter_unpack_sequence
    from restrictedpython.lib import builtins as rbuiltins

    _RESTRICTED_AVAILABLE = True
except ImportError:
    _RESTRICTED_AVAILABLE = False


def _create_safe_globals() -> dict[str, Any]:
    """创建受限执行环境"""
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "__import__": __import__,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_write_": full_write_guard,
    }
    # 允许 math 模块
    import math

    return {"__builtins__": safe_builtins, "math": math}


class SkillImpl(BaseSkill):
    """代码执行 Skill 实现"""

    async def execute(
        self,
        params: dict[str, Any],
        context: SkillContext | None = None,
    ) -> SkillResult:
        if not _RESTRICTED_AVAILABLE:
            return SkillResult(
                success=False,
                error="RestrictedPython 未安装，无法执行代码",
            )

        code = params.get("code", "")
        if not code or not isinstance(code, str):
            return SkillResult(success=False, error="缺少 code 参数")

        try:
            byte_code = compile_restricted_exec(code)
            if byte_code.errors:
                return SkillResult(
                    success=False,
                    error="代码包含不允许的语法: " + "; ".join(byte_code.errors),
                )
        except Exception as e:
            return SkillResult(success=False, error=f"编译失败: {e}")

        globals_dict = _create_safe_globals()
        locals_dict: dict[str, Any] = {}

        # 捕获 print 输出
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = stdout_capture

        try:
            exec(byte_code.code, globals_dict, locals_dict)
            printed = stdout_capture.getvalue().strip()

            # 尝试获取最后一条表达式结果（若代码是单一表达式）
            result = None
            if "result" in locals_dict:
                result = locals_dict["result"]
            elif len(locals_dict) == 1:
                result = next(iter(locals_dict.values()))

            data: dict[str, Any] = {}
            if printed:
                data["output"] = printed
            if result is not None:
                data["result"] = result

            return SkillResult(
                success=True,
                data=data if data else {"message": "执行完成"},
            )
        except Exception as e:
            return SkillResult(success=False, error=f"执行异常: {e}")
        finally:
            sys.stdout = old_stdout
