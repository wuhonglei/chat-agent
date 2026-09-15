"""Regression: FastAPI import order must still register the file MCP server."""

from __future__ import annotations

import subprocess
import sys


def test_app_main_import_registers_file_mcp() -> None:
    script = (
        "from app.main import app\n"
        "from app.mcp import get_mcp_client_manager\n"
        "print(','.join(sorted(get_mcp_client_manager().registry.get_servers())))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    servers_line = proc.stdout.strip().splitlines()[-1]
    servers = servers_line.split(",")
    assert "file" in servers, proc.stdout + "\n" + proc.stderr
