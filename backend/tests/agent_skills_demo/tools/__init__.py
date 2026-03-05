"""Agent Skills Demo 工具集"""

from typing import Any

from .execute_python_code import (
    TOOL_DEF as execute_python_code_def,
)
from .execute_python_code import (
    execute_python_code,
)
from .execute_shell_command import (
    TOOL_DEF as execute_shell_command_def,
)
from .execute_shell_command import (
    execute_shell_command,
)
from .view_text_file import (
    TOOL_DEF as view_text_file_def,
)
from .view_text_file import (
    view_text_file,
)


def get_tools() -> list[dict[str, Any]]:
    """返回 OpenAI 格式的工具定义"""
    return [
        view_text_file_def,
        execute_shell_command_def,
        execute_python_code_def,
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """执行指定工具"""
    if name == "view_text_file":
        return view_text_file(arguments.get("file_path", ""))
    if name == "execute_shell_command":
        return execute_shell_command(
            arguments.get("command", ""),
            cwd=arguments.get("cwd"),
            timeout=arguments.get("timeout", 300),
        )
    if name == "execute_python_code":
        return execute_python_code(arguments.get("code", ""))
    return f"Error: 未知工具 {name}"
