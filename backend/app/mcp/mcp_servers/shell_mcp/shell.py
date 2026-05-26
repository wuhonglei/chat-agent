"""shell tool implementation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.mcp.mcp_servers.shell_mcp.audit import SandboxAuditEntry, log_audit_entry
from app.mcp.mcp_servers.shell_mcp.config import shell_config
from app.mcp.mcp_servers.shell_mcp.executor import SandboxBackendError, ShellExecutor
from app.mcp.mcp_servers.shell_mcp.policy import policy_engine
from app.sandbox.executor import ExecutionResult
from app.vfs.paths import get_paths


class ShellTool:
    """Execute shell commands in sandbox."""

    name = "shell"
    description = "Execute shell commands in a sandboxed environment with proper security measures."

    def __init__(self) -> None:
        self._executors: dict[tuple[str, str], ShellExecutor] = {}
        self._dict_lock = asyncio.Lock()

    async def get_or_create_executor(
        self, user_id: str, conversation_id: str
    ) -> tuple[ShellExecutor | None, str | None]:
        """Return a conversation-scoped executor, creating one on first use."""
        if not (user_id or "").strip():
            return None, "user_id is required for shell execution"
        if not (conversation_id or "").strip():
            return None, "conversation_id is required for shell execution"

        key = (user_id.strip(), conversation_id.strip())
        cached = self._executors.get(key)
        if cached is not None:
            return cached, None

        try:
            workspace_path = get_paths().ensure_sandbox_work_dir(key[0], key[1])
        except ValueError as exc:
            return None, str(exc)

        async with self._dict_lock:
            cached = self._executors.get(key)
            if cached is not None:
                return cached, None

            executor = ShellExecutor()
            try:
                await executor.initialize(
                    workspace_path, user_id=key[0], conversation_id=key[1]
                )
            except SandboxBackendError as exc:
                return None, str(exc)
            self._executors[key] = executor
            return executor, None

    async def initialize(self, workspace_path: Path) -> None:
        """Initialize executor for an explicit path (tests/scripts)."""
        key = ("__explicit__", str(workspace_path.resolve()))
        async with self._dict_lock:
            executor = self._executors.get(key)
            if executor is None:
                executor = ShellExecutor()
                self._executors[key] = executor
            await executor.initialize(workspace_path.resolve())

    async def execute(
        self,
        arguments: dict[str, Any],
        user_id: str,
        conversation_id: str,
    ) -> str:
        """Execute shell tool."""
        command = arguments.get("command", "")
        description = arguments.get("description", "")
        timeout = arguments.get("timeout", shell_config.default_timeout_ms)

        if not command:
            return "Error: command is required"

        if not description:
            return "Error: description is required (5-10 words explaining what the command does)"

        timeout = min(timeout, shell_config.max_timeout_ms)

        policy_decision = policy_engine.validate_command(command)

        if not policy_decision.allowed:
            audit_entry = SandboxAuditEntry(
                user_id=user_id,
                conversation_id=conversation_id,
                command=command,
                description=description,
                decision="blocked",
                block_reason=policy_decision.reason,
            )
            log_audit_entry(audit_entry)

            return (
                f"Error: Command blocked by security policy: {policy_decision.reason}"
            )

        executor, init_error = await self.get_or_create_executor(
            user_id, conversation_id
        )
        if init_error:
            return f"Error: {init_error}"

        assert executor is not None
        result = await executor.execute(
            command=command,
            timeout=timeout,
            description=description,
        )

        output = self._format_output(command, result)

        audit_entry = SandboxAuditEntry(
            user_id=user_id,
            conversation_id=conversation_id,
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

        max_chars = shell_config.max_output_chars
        if len(output) > max_chars:
            output = output[:max_chars] + "\n\n[Output truncated by system limit]"

        return output

    async def cleanup(self) -> None:
        """Cleanup all cached executors."""
        async with self._dict_lock:
            for executor in self._executors.values():
                await executor.cleanup()
            self._executors.clear()
