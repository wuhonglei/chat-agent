"""执行 shell 命令工具，返回 returncode、stdout、stderr"""

import subprocess
from pathlib import Path
from typing import Any

from ._common import DEMO_ROOT


def execute_shell_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 300,
) -> str:
    """执行给定的 shell 命令，返回包含 returncode、stdout、stderr 的 XML 格式结果。

    Args:
        command: 要执行的 shell 命令
        cwd: 工作目录，可为相对路径（相对于 agent_skills_demo 根）或绝对路径
        timeout: 最大执行时间（秒），默认 300

    Returns:
        包含 <returncode>、<stdout>、<stderr> 标签的响应字符串
    """
    run_cwd: Path | None = None
    if cwd:
        p = Path(cwd)
        if not p.is_absolute():
            p = DEMO_ROOT / p
        resolved = p.resolve()
        if str(resolved).startswith(str(DEMO_ROOT.resolve())):
            run_cwd = resolved

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            cwd=run_cwd,
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
        "description": (
            "执行 shell 命令并返回 returncode、stdout、stderr。"
            "执行 skill 中脚本时，务必传入 cwd 为该 skill 目录（如 skills/search），"
            "以便 ./scripts/xxx.sh 等相对路径正确解析。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "cwd": {
                    "type": "string",
                    "description": (
                        "工作目录。相对路径以 agent_skills_demo 根为基准。"
                        "执行 skill 脚本时传入该 skill 的 skill_cwd（如 skills/search）"
                    ),
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
