"""共享路径与校验逻辑，供 view_text_file、execute_shell_command 使用"""

from pathlib import Path

_DEMO_ROOT = Path(__file__).resolve().parent.parent  # agent_skills_demo/
SKILLS_DIR = _DEMO_ROOT / "skills"
BACKEND_ROOT = _DEMO_ROOT.parent.parent  # backend/


def is_path_allowed(path: str) -> bool:
    """校验路径是否在 skills 目录下"""
    try:
        resolved = Path(path).resolve()
        base = SKILLS_DIR.resolve()
        return str(resolved).startswith(str(base))
    except (OSError, ValueError):
        return False
