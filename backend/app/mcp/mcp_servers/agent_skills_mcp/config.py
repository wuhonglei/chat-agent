"""Agent skills MCP server configuration."""

from __future__ import annotations

from pathlib import Path

MAX_WORKSPACE_FILES = 2000
MAX_WORKSPACE_BYTES = 200 * 1024 * 1024
MAX_READ_CHARS = 200_000
MAX_SKILL_BODY_CHARS = 20_000

BACKEND_ROOT = Path(__file__).resolve().parents[4]
USER_DATA_ROOT = BACKEND_ROOT / "data" / "user_data"
