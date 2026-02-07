#!/usr/bin/env python3
"""
Cursor afterFileEdit 钩子：在 AI 编辑文件后对 Python 文件执行 Ruff 格式化。
从 stdin 读取 Cursor 传入的 JSON，对 file_path 为 .py 的文件执行 ruff format 和 ruff check --fix。
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"after_file_edit: invalid JSON from stdin: {e}\n")
        sys.exit(0)  # 不阻塞 Cursor，fail-open

    file_path = payload.get("file_path")
    if not file_path or not isinstance(file_path, str):
        sys.exit(0)

    path = Path(file_path)
    if not path.suffix == ".py" or not path.exists():
        sys.exit(0)

    # 在项目根目录执行 ruff，以便使用 pyproject.toml 配置
    workspace_roots = payload.get("workspace_roots") or []
    cwd = Path(workspace_roots[0]) if workspace_roots else path.parent

    for cmd in (
        ["ruff", "check", "--fix", str(path)],
        ["ruff", "format", str(path)],
    ):
        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            sys.stderr.write(f"after_file_edit: {cmd[0]} failed: {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
