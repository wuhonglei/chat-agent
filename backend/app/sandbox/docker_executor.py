"""Docker-based sandbox executor."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.sandbox.executor import ExecutionRequest, ExecutionResult, SandboxExecutor
from app.utils.logger import logger
from app.vfs.config import SKILLS_PUBLIC_DIR, vfs_config


class DockerSandboxExecutor(SandboxExecutor):
    """Execute commands in isolated Docker containers."""

    def __init__(self) -> None:
        self._workspace_path: Path | None = None
        self._uploads_path: Path | None = None
        self._outputs_path: Path | None = None
        self._user_skills_path: Path | None = None
        self._skills_public_path: Path | None = None

    async def setup(self, workspace_path: Path) -> None:
        """Setup workspace path for container mounts."""
        self._workspace_path = workspace_path.resolve()
        self._workspace_path.mkdir(parents=True, exist_ok=True)

    async def set_uploads_path(self, uploads_path: Path) -> None:
        """Set conversation uploads path for read-only mount."""
        self._uploads_path = uploads_path.resolve()

    async def set_outputs_path(self, outputs_path: Path) -> None:
        """Set conversation outputs path for read-write mount."""
        self._outputs_path = outputs_path.resolve()
        self._outputs_path.mkdir(parents=True, exist_ok=True)

    async def set_user_skills_path(self, user_skills_path: Path) -> None:
        """Set per-user custom skills path for read-write mount at /mnt/skills/custom."""
        self._user_skills_path = user_skills_path.resolve()
        self._user_skills_path.mkdir(parents=True, exist_ok=True)

    async def set_skills_public_path(
        self, skills_public_path: Path | None = None
    ) -> None:
        """Set built-in public skills path for read-only mount at /mnt/skills/public."""
        path = (skills_public_path or SKILLS_PUBLIC_DIR).resolve()
        self._skills_public_path = path if path.exists() else None

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
            container_config = self._build_container_config(request)

            timeout_sec = min(request.timeout / 1000, 600)
            container = await asyncio.to_thread(
                client.containers.run,
                **container_config,
            )

            try:
                result = await asyncio.to_thread(container.wait, timeout=timeout_sec)

                stdout = await asyncio.to_thread(
                    container.logs, stdout=True, stderr=False
                )
                stderr = await asyncio.to_thread(
                    container.logs, stdout=False, stderr=True
                )

                stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
                stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

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
        workspace_target = vfs_config.workspace_prefix.rstrip("/")
        uploads_target = vfs_config.uploads_prefix.rstrip("/")
        outputs_target = vfs_config.outputs_prefix.rstrip("/")

        if self._workspace_path:
            mounts.append(
                {
                    "source": str(self._workspace_path),
                    "target": workspace_target,
                    "type": "bind",
                    "read_only": False,
                }
            )

        if self._uploads_path and self._uploads_path.exists():
            mounts.append(
                {
                    "source": str(self._uploads_path),
                    "target": uploads_target,
                    "type": "bind",
                    "read_only": True,
                }
            )

        if self._outputs_path:
            self._outputs_path.mkdir(parents=True, exist_ok=True)
            mounts.append(
                {
                    "source": str(self._outputs_path),
                    "target": outputs_target,
                    "type": "bind",
                    "read_only": False,
                }
            )

        skills_custom_target = vfs_config.skills_custom_prefix.rstrip("/")
        if self._user_skills_path:
            mounts.append(
                {
                    "source": str(self._user_skills_path),
                    "target": skills_custom_target,
                    "type": "bind",
                    "read_only": False,
                }
            )

        skills_public_target = vfs_config.skills_public_prefix.rstrip("/")
        if self._skills_public_path and self._skills_public_path.exists():
            mounts.append(
                {
                    "source": str(self._skills_public_path),
                    "target": skills_public_target,
                    "type": "bind",
                    "read_only": True,
                }
            )

        env = {
            "HOME": workspace_target,
            "TMPDIR": "/tmp",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "USER_SKILLS_DIR": skills_custom_target,
        }
        if request.env:
            env.update(request.env)

        return {
            "image": settings.sandbox.image,
            "command": ["bash", "-c", request.command],
            "working_dir": request.cwd,
            "detach": True,
            "environment": env,
            "mounts": mounts,
            "network_disabled": not settings.sandbox.network_enabled,
            "nano_cpus": int(settings.sandbox.cpu_limit * 1e9),
            "mem_limit": settings.sandbox.memory_limit,
            "pids_limit": settings.sandbox.pid_limit,
            "read_only": False,
            "user": "1000:1000",
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "tmpfs": {"/tmp": "size=100m"},
        }

    async def cleanup(self) -> None:
        """Cleanup Docker resources."""
        self._workspace_path = None
        self._uploads_path = None
        self._outputs_path = None
        self._user_skills_path = None
        self._skills_public_path = None
