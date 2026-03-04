"""执行 shell 命令工具，返回 returncode、stdout、stderr"""

import subprocess
from typing import Any


def execute_shell_command(command: str, timeout: int = 300) -> str:
    """执行给定的 shell 命令，返回包含 returncode、stdout、stderr 的 XML 格式结果。

    Args:
        command: 要执行的 shell 命令
        timeout: 最大执行时间（秒），默认 300

    Returns:
        包含 <returncode>、<stdout>、<stderr> 标签的响应字符串
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        returncode = result.returncode
        stdout_str = result.stdout or ""
        stderr_str = result.stderr or ""

    except subprocess.TimeoutExpired:
        stderr_suffix = f"TimeoutError: 命令执行超过超时限制 {timeout} 秒。"
        returncode = -1
        stdout_str = ""
        stderr_str = stderr_suffix

    return (
        f"<returncode>{returncode}</returncode>"
        f"<stdout>{stdout_str}</stdout>"
        f"<stderr>{stderr_str}</stderr>"
    )


TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_shell_command",
        "description": "执行 shell 命令并返回 returncode、stdout、stderr。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "最大执行时间（秒），默认 300",
                    "default": 300,
                },
            },
            "required": ["command"],
        },
    },
}
