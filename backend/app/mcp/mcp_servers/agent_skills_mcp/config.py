"""Agent skills MCP server configuration."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_SEGMENTS = {
    ".git",
    ".ssh",
    ".aws",
    ".cursor",
    "__pycache__",
}

DANGEROUS_BASH_PATTERNS = (
    " rm -rf /",
    " rm -rf /*",
    " rm -rf ~/",
    ":(){",
    "mkfs.",
    "dd if=/dev/zero",
    "shutdown ",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    "sudo ",
    "su ",
    "chmod -r 777 /",
    "chown -r ",
    "| sh",
    "| bash",
    "bash -c",
    "nc -e",
    "ncat -e",
    "/dev/tcp/",
)

MAX_WORKSPACE_BYTES = 2000 * 1024 * 1024
MAX_READ_CHARS = 200_000
MAX_SKILL_BODY_CHARS = 20_000

BACKEND_ROOT = Path(__file__).resolve().parents[4]
USER_DATA_ROOT = BACKEND_ROOT / "data" / "user_data"
