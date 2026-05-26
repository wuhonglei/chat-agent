"""Local sandbox executor for development mode."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from pathlib import Path

from app.core.config import settings
from app.sandbox.executor import ExecutionRequest, ExecutionResult, SandboxExecutor
from app.utils.logger import logger


class LocalSandboxExecutor(SandboxExecutor):
    """Execute commands locally with process group isolation.

    Used when sandbox.backend is set to local (e.g. development without Docker).
    Still applies policy engine filtering before execution.
    """

    def __init__(self) -> None:
        self._workspace_path: Path | None = None

    async def setup(self, workspace_path: Path) -> None:
        """Setup workspace path."""
        self._workspace_path = workspace_path.resolve()
        self._workspace_path.mkdir(parents=True, exist_ok=True)

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute command locally with process group management."""
        if not self._workspace_path:
            return ExecutionResult(
                blocked=True,
                block_reason="Sandbox not initialized. Call setup() first.",
            )

        start_time = time.monotonic()
        timeout_sec = min(request.timeout / 1000, 600)  # max 600s

        try:
            # Create process with session ID for process group management
            process = await asyncio.create_subprocess_shell(
                request.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=request.cwd,
                env={
                    **os.environ,
                    "HOME": str(self._workspace_path),
                    "TMPDIR": "/tmp",
                    **(request.env or {}),
                },
                preexec_fn=os.setsid,  # Create new process group
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_sec,
                )
                timed_out = False
            except asyncio.TimeoutError:
                # Kill entire process group
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    await asyncio.sleep(0.5)
                    if process.returncode is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass

                stdout_bytes, stderr_bytes = b"", b""
                timed_out = True

            stdout = (
                stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            )
            stderr = (
                stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            )

            # Truncate output if needed
            output_truncated = False
            max_output = settings.sandbox.output_limit
            if len(stdout) + len(stderr) > max_output:
                stdout = stdout[: max_output // 2]
                stderr = stderr[: max_output // 2]
                output_truncated = True

            duration_ms = int((time.monotonic() - start_time) * 1000)

            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                return_code=process.returncode or 0,
                timed_out=timed_out,
                duration_ms=duration_ms,
                output_truncated=output_truncated,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Local sandbox execution failed", error=e, exc_info=True)
            return ExecutionResult(
                stderr=f"Sandbox execution error: {e}",
                return_code=1,
                duration_ms=duration_ms,
            )

    async def cleanup(self) -> None:
        """Cleanup local resources."""
        self._workspace_path = None
