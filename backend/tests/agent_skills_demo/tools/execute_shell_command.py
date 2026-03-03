"""执行 shell 命令工具，仅允许 cat/head/tail 读取 skills 目录内文件"""

import re
import subprocess
from pathlib import Path
from typing import Any

from ._common import BACKEND_ROOT, SKILLS_DIR, is_path_allowed


def execute_shell_command(command: str) -> str:
    """执行 shell 命令，仅允许 cat/head/tail，且路径必须在 skills 目录内"""
    stripped = command.strip()
    match = re.match(r"^(cat|head|tail)(?:\s+(-[^\s]+))?\s+(.+)$", stripped)
    if not match:
        return "Error: 仅允许 cat、head、tail 命令，用于读取文件"
    cmd, opts, path_part = match.groups()
    opts = (opts or "").strip()
    path_str = path_part.strip().strip("'\"")
    abs_path = Path(path_str)
    if not abs_path.is_absolute():
        abs_path = (SKILLS_DIR / path_str).resolve()
    if not is_path_allowed(str(abs_path)):
        return f"Error: 路径不在允许范围内，仅能读取 {SKILLS_DIR}"
    try:
        args = [cmd]
        if opts:
            args.append(opts)
        args.append(str(abs_path))
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(BACKEND_ROOT),
        )
        out = result.stdout or result.stderr or ""
        return out.strip() if out else "(空输出)"
    except subprocess.TimeoutExpired:
        return "Error: 命令执行超时"
    except Exception as e:
        return f"Error: 执行失败 - {e}"


TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_shell_command",
        "description": "执行 shell 命令。仅支持 cat、head、tail 读取文件，路径必须在 skills 目录内。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "命令，如 'cat path/to/file'",
                },
            },
            "required": ["command"],
        },
    },
}
