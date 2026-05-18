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
        self._initialized = False

    async def initialize(self, workspace_path: Path) -> None:
        """Initialize the sandbox executor."""
        if sandbox_config.backend == "docker":
            self._executor = DockerSandboxExecutor()
        else:
            self._executor = LocalSandboxExecutor()

        await self._executor.setup(workspace_path)
        self._initialized = True

        logger.info(
            "Shell executor initialized",
            backend=sandbox_config.backend,
            workspace=str(workspace_path),
        )

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        timeout: int = 30000,
        description: str = "",
    ) -> ExecutionResult:
        """Execute a command in sandbox."""
        if not self._initialized or not self._executor:
            return ExecutionResult(
                blocked=True,
                block_reason="Executor not initialized",
            )

        request = ExecutionRequest(
            command=command,
            cwd=cwd,
            timeout=min(timeout, sandbox_config.timeout),
            description=description,
        )

        return await self._executor.execute(request)

    async def cleanup(self) -> None:
        """Cleanup executor resources."""
        if self._executor:
            await self._executor.cleanup()
        self._initialized = False
