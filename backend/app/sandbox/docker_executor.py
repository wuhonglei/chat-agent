"""Docker-based sandbox executor."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.sandbox.executor import ExecutionRequest, ExecutionResult, SandboxExecutor
from app.utils.logger import logger


class DockerSandboxExecutor(SandboxExecutor):
    """Execute commands in isolated Docker containers."""

    def __init__(self) -> None:
        self._workspace_path: Path | None = None
        self._uploads_path: Path | None = None

    async def setup(self, workspace_path: Path) -> None:
        """Setup workspace path for container mounts."""
        self._workspace_path = workspace_path.resolve()
        self._workspace_path.mkdir(parents=True, exist_ok=True)

    async def set_uploads_path(self, uploads_path: Path) -> None:
        """Set uploads path for read-only mount."""
        self._uploads_path = uploads_path.resolve()

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute command in Docker container with security constraints."""
        if not self._workspace_path:
            return ExecutionResult(
                blocked=True,
                block_reason="Sandbox not initialized. Call setup() first.",
            )

        start_time = time.monotonic()

        try:
            import docker

            client = docker.from_env()

            # Build container configuration
            container_config = self._build_container_config(request)

            # Run container
            timeout_sec = min(request.timeout / 1000, 600)  # max 600s
            container = await asyncio.to_thread(
                client.containers.run,
                **container_config,
            )

            try:
                # Wait for container to finish with timeout
                result = await asyncio.to_thread(container.wait, timeout=timeout_sec)

                # Get logs
                stdout = await asyncio.to_thread(
                    container.logs, stdout=True, stderr=False
                )
                stderr = await asyncio.to_thread(
                    container.logs, stdout=False, stderr=True
                )

                stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
                stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

                # Truncate output if needed
                output_truncated = False
                max_output = settings.sandbox.output_limit
                if len(stdout_str) + len(stderr_str) > max_output:
                    stdout_str = stdout_str[: max_output // 2]
                    stderr_str = stderr_str[: max_output // 2]
                    output_truncated = True

                duration_ms = int((time.monotonic() - start_time) * 1000)

                return ExecutionResult(
                    stdout=stdout_str,
                    stderr=stderr_str,
                    return_code=result.get("StatusCode", 1),
                    timed_out=False,
                    duration_ms=duration_ms,
                    output_truncated=output_truncated,
                )

            finally:
                # Always remove container
                try:
                    await asyncio.to_thread(container.remove, force=True)
                except Exception:
                    pass

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Docker sandbox execution failed", error=e, exc_info=True)
            return ExecutionResult(
                stderr=f"Sandbox execution error: {e}",
                return_code=1,
                duration_ms=duration_ms,
            )

    def _build_container_config(self, request: ExecutionRequest) -> dict[str, Any]:
        """Build Docker container run configuration."""
        mounts = []

        # Workspace mount (read-write)
        if self._workspace_path:
            mounts.append(
                {
                    "source": str(self._workspace_path),
                    "target": "/workspace",
                    "type": "bind",
                    "read_only": False,
                }
            )

        # Uploads mount (read-only)
        if self._uploads_path and self._uploads_path.exists():
            mounts.append(
                {
                    "source": str(self._uploads_path),
                    "target": "/uploads",
                    "type": "bind",
                    "read_only": True,
                }
            )

        # Environment variables
        env = {
            "HOME": "/workspace",
            "TMPDIR": "/tmp",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        }
        if request.env:
            env.update(request.env)

        config = {
            "image": settings.sandbox.image,
            "command": ["bash", "-c", request.command],
            "working_dir": request.cwd,
            "detach": True,
            "environment": env,
            "mounts": mounts,
            # Security constraints (aligned with kimi)
            "network_disabled": not settings.sandbox.network_enabled,
            "nano_cpus": int(settings.sandbox.cpu_limit * 1e9),
            "mem_limit": settings.sandbox.memory_limit,
            "pids_limit": settings.sandbox.pid_limit,
            "read_only": False,  # workspace bind mount is RW; allow writes under /workspace
            "user": "1000:1000",  # Non-root execution
            "cap_drop": ["ALL"],  # Drop all capabilities
            "security_opt": ["no-new-privileges"],  # Prevent privilege escalation
            "tmpfs": {"/tmp": "size=100m"},  # Writable tmp
        }

        return config

    async def cleanup(self) -> None:
        """Cleanup Docker resources."""
        self._workspace_path = None
        self._uploads_path = None
