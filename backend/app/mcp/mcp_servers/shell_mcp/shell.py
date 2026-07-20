"""shell tool implementation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.mcp.mcp_servers.shell_mcp.audit import SandboxAuditEntry, log_audit_entry
from app.mcp.mcp_servers.shell_mcp.command_audit import (
    audit_command,
    format_medium_risk_warning,
)
from app.mcp.mcp_servers.shell_mcp.config import shell_config
from app.mcp.mcp_servers.shell_mcp.executor import SandboxBackendError, ShellExecutor
from app.mcp.mcp_servers.shell_mcp.models import ShellToolExecuteResult
from app.sandbox.executor import ExecutionResult
from app.schemas.shell_display import ShellExecStructuredContent
from app.vfs.paths import get_paths


class ShellTool:
    """Execute shell commands in sandbox."""

    name = "exec"
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
            paths = get_paths()
            paths.ensure_conversation_dirs(key[0], key[1])
            workspace_path = paths.sandbox_work_dir(key[0], key[1]).resolve()
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
    ) -> ShellToolExecuteResult:
        """Execute shell tool."""
        command = arguments.get("command", "")
        raw_timeout = arguments.get("timeout", shell_config.default_timeout_ms)

        if not command:
            return ShellToolExecuteResult(content="Error: command is required")

        try:
            timeout = int(raw_timeout)
        except (TypeError, ValueError):
            return ShellToolExecuteResult(
                content=f"Error: invalid timeout value: {raw_timeout!r}"
            )

        timeout = min(timeout, shell_config.max_timeout_ms)

        audit_result = audit_command(command)

        if audit_result.verdict == "block":
            log_audit_entry(
                SandboxAuditEntry(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    command=command,
                    verdict="block",
                    block_reason=audit_result.reason,
                )
            )
            reason = audit_result.reason or "security violation detected"
            return ShellToolExecuteResult(content=f"Error: Command blocked: {reason}")

        executor, init_error = await self.get_or_create_executor(
            user_id, conversation_id
        )
        if init_error:
            return ShellToolExecuteResult(content=f"Error: {init_error}")

        assert executor is not None
        result = await executor.execute(
            command=command,
            timeout=timeout,
        )

        output = self._format_output(command, result)
        structured = self._build_structured_content(result)

        if audit_result.verdict == "warn":
            output += format_medium_risk_warning(command)

        log_audit_entry(
            SandboxAuditEntry(
                user_id=user_id,
                conversation_id=conversation_id,
                command=command,
                verdict=audit_result.verdict,
                return_code=result.return_code,
                duration_ms=result.duration_ms,
                output_size=len(output),
            )
        )

        return ShellToolExecuteResult(content=output, structured_content=structured)

    @staticmethod
    def _build_structured_content(
        result: ExecutionResult,
    ) -> ShellExecStructuredContent:
        return ShellExecStructuredContent(
            exit_code=result.return_code,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            timed_out=result.timed_out,
            output_truncated=result.output_truncated,
            blocked=result.blocked,
            block_reason=result.block_reason,
            duration_ms=result.duration_ms,
        )

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
