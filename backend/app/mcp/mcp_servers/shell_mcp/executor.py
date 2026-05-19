"""Sandbox executor integration for shell MCP."""

from __future__ import annotations

from pathlib import Path

from app.sandbox.config import sandbox_config
from app.sandbox.docker_executor import DockerSandboxExecutor
from app.sandbox.executor import ExecutionRequest, ExecutionResult, SandboxExecutor
from app.sandbox.local_executor import LocalSandboxExecutor
from app.utils.logger import logger


class ShellExecutor:
    """Wrapper around SandboxExecutor for shell MCP integration."""

    def __init__(self) -> None:
        self._executor: SandboxExecutor | None = None
        self._workspace_path: Path | None = None
        self._initialized = False

    async def initialize(
        self, workspace_path: Path, *, user_id: str | None = None
    ) -> None:
        """Initialize the sandbox executor for a workspace path."""
        resolved = workspace_path.resolve()

        if (
            self._initialized
            and self._executor is not None
            and self._workspace_path == resolved
        ):
            return

        if sandbox_config.backend == "docker":
            if not isinstance(self._executor, DockerSandboxExecutor):
                self._executor = DockerSandboxExecutor()
        elif not isinstance(self._executor, LocalSandboxExecutor):
            self._executor = LocalSandboxExecutor()

        assert self._executor is not None
        await self._executor.setup(resolved)

        if user_id and isinstance(self._executor, DockerSandboxExecutor):
            from app.mcp.mcp_servers.file_mcp.utils import get_uploads_root

            await self._executor.set_uploads_path(get_uploads_root(user_id))

        self._workspace_path = resolved
        self._initialized = True

        logger.info(
            "Shell executor initialized",
            backend=sandbox_config.backend,
            workspace=str(resolved),
        )

    def _resolve_cwd(self) -> str:
        if sandbox_config.backend == "docker":
            return "/workspace"
        if self._workspace_path is None:
            return "/workspace"
        return str(self._workspace_path)

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        timeout: int = 30000,
        description: str = "",
    ) -> ExecutionResult:
        """Execute a command in sandbox."""
        _ = cwd  # cwd is derived from backend + workspace_path
        if not self._initialized or not self._executor:
            return ExecutionResult(
                blocked=True,
                block_reason="Executor not initialized",
            )

        request = ExecutionRequest(
            command=command,
            cwd=self._resolve_cwd(),
            timeout=min(timeout, sandbox_config.timeout),
            description=description,
        )

        return await self._executor.execute(request)

    async def cleanup(self) -> None:
        """Cleanup executor resources."""
        if self._executor:
            await self._executor.cleanup()
        self._executor = None
        self._workspace_path = None
        self._initialized = False
