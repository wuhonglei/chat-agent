"""Tests for shell MCP server."""

from __future__ import annotations

import pytest

from app.mcp.mcp_servers.shell_mcp.policy import CommandPolicyEngine


@pytest.fixture
def policy() -> CommandPolicyEngine:
    return CommandPolicyEngine()


def test_policy_empty_command(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("")
    assert not result.allowed
    assert "empty" in result.reason.lower()


def test_policy_blocked_command(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("sudo ls")
    assert not result.allowed
    assert "blocked" in result.reason.lower()


def test_policy_allowed_command(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("ls -la")
    assert result.allowed


def test_policy_dangerous_rm_rf(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("rm -rf /")
    assert not result.allowed


def test_policy_pipe_to_shell(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("echo hello | sh")
    assert not result.allowed


def test_policy_fork_bomb(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command(":(){ :|:& };:")
    assert not result.allowed


def test_policy_git_allowed(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("git status")
    assert result.allowed


def test_policy_python_allowed(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("python --version")
    assert result.allowed


def test_policy_npm_allowed(policy: CommandPolicyEngine) -> None:
    result = policy.validate_command("npm install")
    assert result.allowed
