"""读取文本文件工具，仅允许 skills 目录下的路径"""

from pathlib import Path
from typing import Any

from ._common import SKILLS_DIR, is_path_allowed


def view_text_file(file_path: str) -> str:
    """读取文本文件内容，仅允许 skills 目录下的路径"""
    abs_path = Path(file_path)
    if not abs_path.is_absolute():
        abs_path = (SKILLS_DIR / file_path).resolve()
    if not is_path_allowed(str(abs_path)):
        return f"Error: 路径不在允许范围内，仅能读取 {SKILLS_DIR}"
    try:
        return abs_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: 读取文件失败 - {e}"


TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "view_text_file",
        "description": "读取文本文件内容。仅能读取 skills 目录下的文件，用于查看 SKILL.md 等。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径，相对于 skills 目录或绝对路径",
                },
            },
            "required": ["file_path"],
        },
    },
}
