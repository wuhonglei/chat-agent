"""安全执行 Python 代码工具，使用 RestrictedPython"""

import datetime
import json
import math
import time
import urllib.request
from typing import Any

from RestrictedPython.compile import compile_restricted_exec
from RestrictedPython.Guards import safe_builtins
from RestrictedPython.PrintCollector import PrintCollector


class _CapturingPrintCollector(PrintCollector):  # type: ignore[misc]
    """收集 print 输出到 output_parts"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.output_parts: list[str] = []

    def write(self, text: str) -> None:
        self.output_parts.append(text)
        super().write(text)


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    """仅允许导入 math、json、urllib.request、datetime、time"""
    allowed = {
        "math": math,
        "json": json,
        "urllib.request": urllib.request,
        "datetime": datetime,
        "time": time,
    }
    if name in allowed:
        return allowed[name]
    raise ImportError(f"不允许导入模块: {name}")


def execute_python_code(code: str) -> str:
    """使用 RestrictedPython 安全执行 Python 代码"""
    safe = dict(safe_builtins)
    safe["__import__"] = _safe_import
    restricted_globals: dict[str, Any] = {
        "__builtins__": safe,
        "__name__": "__main__",
        "_print_": _CapturingPrintCollector,
        "math": math,
        "json": json,
        "datetime": datetime,
        "time": time,
    }
    try:
        result = compile_restricted_exec(code, filename="<inline>")
        if result.errors:
            return f"Error: 编译错误 - {result.errors}"
        if result.code is None:
            return "Error: 编译失败"
        exec(result.code, restricted_globals)
        if "result" in restricted_globals:
            return str(restricted_globals["result"])
        if "printed" in restricted_globals:
            return str(restricted_globals["printed"]).strip()
        for v in restricted_globals.values():
            if isinstance(v, _CapturingPrintCollector) and v.output_parts:
                return "".join(v.output_parts).strip()
        return "(代码已执行，无输出。请使用 print() 输出结果)"
    except Exception as e:
        return f"Error: 执行失败 - {e}"


TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_python_code",
        "description": "安全执行 Python 代码。支持 math、json、urllib.request、datetime、time 模块，使用 print() 输出结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python 代码",
                },
            },
            "required": ["code"],
        },
    },
}
