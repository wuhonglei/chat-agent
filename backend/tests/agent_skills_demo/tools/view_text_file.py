"""读取文本文件工具，仅允许 skills 目录下的路径"""

from pathlib import Path
from typing import Any

from ._common import DEMO_ROOT, SKILLS_DIR, is_path_allowed


def view_text_file(file_path: str) -> str:
    """读取文本文件内容，仅允许 skills 目录下的路径"""
    abs_path = Path(file_path)
    if not abs_path.is_absolute():
        if file_path.startswith("skills/") or file_path.startswith("skills\\"):
            abs_path = (DEMO_ROOT / file_path).resolve()
        else:
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
                    "description": "文件路径。支持：相对于 agent_skills_demo 根（如 skills/search/SKILL.md）、相对于 skills 目录、或绝对路径",
                },
            },
            "required": ["file_path"],
        },
    },
}
