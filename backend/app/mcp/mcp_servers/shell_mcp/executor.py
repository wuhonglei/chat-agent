"""Sandbox executor integration for shell MCP."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.sandbox.docker_availability import is_docker_daemon_available
from app.sandbox.docker_executor import DockerSandboxExecutor
from app.sandbox.executor import ExecutionRequest, ExecutionResult, SandboxExecutor
from app.sandbox.local_executor import LocalSandboxExecutor
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths


class ShellExecutor:
    """Wrapper around SandboxExecutor for shell MCP integration."""

    def __init__(self) -> None:
        self._executor: SandboxExecutor | None = None
        self._workspace_path: Path | None = None
        self._effective_backend: str = settings.sandbox.backend
        self._initialized = False

    def _resolve_backend(self) -> str:
        configured = settings.sandbox.backend
        if configured == "docker" and not is_docker_daemon_available():
            logger.warning(
                "Docker daemon unavailable, falling back to local sandbox",
                configured_backend=configured,
            )
            return "local"
        return configured

    def _create_sandbox_executor(self, backend: str) -> SandboxExecutor:
        if backend == "docker":
            return DockerSandboxExecutor()
        return LocalSandboxExecutor()

    async def initialize(
        self,
        workspace_path: Path,
        *,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        """Initialize the sandbox executor for a conversation workspace path."""
        resolved = workspace_path.resolve()
        backend = self._resolve_backend()

        if (
            self._initialized
            and self._executor is not None
            and self._workspace_path == resolved
            and self._effective_backend == backend
        ):
            return

        self._effective_backend = backend
        if not isinstance(
            self._executor,
            DockerSandboxExecutor if backend == "docker" else LocalSandboxExecutor,
        ):
            self._executor = self._create_sandbox_executor(backend)

        assert self._executor is not None
        await self._executor.setup(resolved)

        if (
            user_id
            and conversation_id
            and isinstance(self._executor, DockerSandboxExecutor)
        ):
            uploads_dir = get_paths().sandbox_uploads_dir(user_id, conversation_id)
            outputs_dir = get_paths().sandbox_outputs_dir(user_id, conversation_id)
            await self._executor.set_uploads_path(uploads_dir)
            await self._executor.set_outputs_path(outputs_dir)

        self._workspace_path = resolved
        self._initialized = True

        logger.info(
            "Shell executor initialized",
            backend=self._effective_backend,
            workspace=str(resolved),
        )

    def _workspace_mount_prefix(self) -> str:
        if self._effective_backend == "docker":
            return vfs_config.workspace_prefix.rstrip("/")
        if self._workspace_path is None:
            return vfs_config.workspace_prefix.rstrip("/")
        return str(self._workspace_path)

    def _resolve_cwd(self) -> str:
        return self._workspace_mount_prefix()

    def _adapt_command_for_backend(self, command: str) -> str:
        """Drop redundant workspace cd/mkdir; cwd is already the workspace root."""
        prefix = re.escape(self._workspace_mount_prefix())
        adapted = command
        adapted = re.sub(
            rf"^\s*mkdir\s+(?:-p\s+)?{prefix}\s*(?:&&|;)\s*",
            "",
            adapted,
            count=1,
        )
        adapted = re.sub(
            rf"^\s*cd\s+{prefix}\s*(?:&&|;)\s*",
            "",
            adapted,
            count=1,
        )
        adapted = re.sub(rf"^\s*cd\s+{prefix}\s*$", ".", adapted)
        return adapted.strip() or "true"

    async def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 30000,
        description: str = "",
    ) -> ExecutionResult:
        """Execute a command in sandbox."""
        _ = cwd
        if not self._initialized or not self._executor:
            return ExecutionResult(
                blocked=True,
                block_reason="Executor not initialized",
            )

        request = ExecutionRequest(
            command=self._adapt_command_for_backend(command),
            cwd=self._resolve_cwd(),
            timeout=min(timeout, settings.sandbox.timeout),
            description=description,
        )

        return await self._executor.execute(request)

    async def cleanup(self) -> None:
        """Cleanup executor resources."""
        if self._executor:
            await self._executor.cleanup()
        self._executor = None
        self._workspace_path = None
        self._effective_backend = settings.sandbox.backend
        self._initialized = False
