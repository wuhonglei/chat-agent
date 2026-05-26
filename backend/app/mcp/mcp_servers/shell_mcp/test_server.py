"""Tests for shell MCP command audit (replaces legacy policy whitelist tests)."""

from __future__ import annotations

from app.mcp.mcp_servers.shell_mcp.command_audit import audit_command, classify_command


def test_audit_empty_command() -> None:
    result = audit_command("")
    assert result.verdict == "block"
    assert result.reason == "empty command"


def test_audit_rm_rf_blocked() -> None:
    result = audit_command("rm -rf /")
    assert result.verdict == "block"


def test_audit_pipe_to_shell_blocked() -> None:
    result = audit_command("echo hello | sh")
    assert result.verdict == "block"


def test_audit_fork_bomb_blocked() -> None:
    result = audit_command(":(){ :|:& };:")
    assert result.verdict == "block"


def test_audit_git_allowed() -> None:
    result = audit_command("git status")
    assert result.verdict == "pass"


def test_audit_python_allowed() -> None:
    result = audit_command("python --version")
    assert result.verdict == "pass"


def test_audit_pip_install_warns() -> None:
    result = audit_command("pip install requests")
    assert result.verdict == "warn"


def test_audit_vite_scaffold_allowed() -> None:
    command = (
        "npx --yes create-vite@latest vite-tmp --template react-ts && "
        "cd vite-tmp && npm install && npm run build"
    )
    assert classify_command(command) == "pass"


def test_audit_curl_allowed() -> None:
    result = audit_command("curl https://example.com")
    assert result.verdict == "pass"


def test_audit_chained_command_blocks_dangerous_segment() -> None:
    result = audit_command("ls -la && rm -rf /")
    assert result.verdict == "block"
