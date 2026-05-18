"""shell tool implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.mcp.mcp_servers.shell_mcp.audit import SandboxAuditEntry, log_audit_entry
from app.mcp.mcp_servers.shell_mcp.config import shell_config
from app.mcp.mcp_servers.shell_mcp.executor import ShellExecutor
from app.mcp.mcp_servers.shell_mcp.policy import policy_engine
from app.sandbox.executor import ExecutionResult


class ShellTool:
    """Execute shell commands in sandbox."""

    name = "shell"
    description = "Execute shell commands in a sandboxed environment with proper security measures."

    def __init__(self) -> None:
        self._executor = ShellExecutor()

    async def initialize(self, workspace_path: Path) -> None:
        """Initialize the shell executor."""
        await self._executor.initialize(workspace_path)

    async def execute(
        self,
        arguments: dict[str, Any],
        user_id: str,
        workspace_id: str,
    ) -> str:
        """Execute shell tool."""
        command = arguments.get("command", "")
        description = arguments.get("description", "")
        timeout = arguments.get("timeout", shell_config.default_timeout_ms)

        if not command:
            return "Error: command is required"

        if not description:
            return "Error: description is required (5-10 words explaining what the command does)"

        # Validate timeout
        timeout = min(timeout, shell_config.max_timeout_ms)

        # Apply policy engine
        policy_decision = policy_engine.validate_command(command)

        if not policy_decision.allowed:
            # Log blocked command
            audit_entry = SandboxAuditEntry(
                user_id=user_id,
                workspace_id=workspace_id,
                command=command,
                description=description,
                decision="blocked",
                block_reason=policy_decision.reason,
            )
            log_audit_entry(audit_entry)

            return (
                f"Error: Command blocked by security policy: {policy_decision.reason}"
            )

        # Execute in sandbox
        result = await self._executor.execute(
            command=command,
            cwd="/workspace",
            timeout=timeout,
            description=description,
        )

        # Build output
        output = self._format_output(command, result)

        # Log execution
        audit_entry = SandboxAuditEntry(
            user_id=user_id,
            workspace_id=workspace_id,
            command=command,
            description=description,
            decision="allowed",
            return_code=result.return_code,
            duration_ms=result.duration_ms,
            output_size=len(output),
        )
        log_audit_entry(audit_entry)

        return output

    def _format_output(self, command: str, result: ExecutionResult) -> str:
        """Format execution result as output string."""
        parts = [f"$ {command}"]

        if result.blocked:
            parts.append(f"[blocked] {result.block_reason}")
            return "\n".join(parts)

        parts.append(f"[exit_code={result.return_code}]")

        if result.timed_out:
            parts.append("[timed_out=true]")

        if result.output_truncated:
            parts.append("[output_truncated=true]")

        parts.append("")
        parts.append("--- stdout ---")
        parts.append(result.stdout or "(empty)")

        if result.stderr:
            parts.append("")
            parts.append("--- stderr ---")
            parts.append(result.stderr)

        output = "\n".join(parts)

        # Truncate if needed
        max_chars = shell_config.max_output_chars
        if len(output) > max_chars:
            output = output[:max_chars] + "\n\n[Output truncated by system limit]"

        return output

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self._executor.cleanup()
