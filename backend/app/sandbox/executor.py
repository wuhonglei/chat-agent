"""Abstract sandbox executor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionRequest:
    """Request to execute a command in sandbox."""

    command: str
    cwd: str = "/workspace"
    timeout: int = 600000  # ms, max 600000 (10 minutes)
    env: dict[str, str] | None = None
    description: str = ""  # LLM must describe command purpose for audit


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""

    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    timed_out: bool = False
    blocked: bool = False
    block_reason: str | None = None
    duration_ms: int = 0
    output_truncated: bool = False

    @property
    def combined_output(self) -> str:
        """Combined stdout + stderr output."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


class SandboxExecutor(ABC):
    """Abstract base class for sandbox executors."""

    @abstractmethod
    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a command in sandbox."""

    @abstractmethod
    async def setup(self, workspace_path: Path) -> None:
        """Setup sandbox environment with workspace."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup sandbox resources."""
