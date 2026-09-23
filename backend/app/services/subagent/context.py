"""Request-scoped delegation context and audit buffer.

The audit list is created on the parent turn and copied by reference into
tool tasks (``asyncio.ensure_future`` copies the context, not the list).
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.schemas.config import LLMConfig

_turn_delegation: ContextVar[TurnDelegationContext | None] = ContextVar(
    "turn_delegation",
    default=None,
)
_subagent_runs: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "subagent_runs",
    default=None,
)


@dataclass(frozen=True, slots=True)
class TurnDelegationContext:
    """Snapshot of the turn that may call ``delegate_task``."""

    llm_config: LLMConfig
    agent_mode: int
    language: str | None
    think_mode: bool
    mcp_server_names: list[str]


def set_turn_delegation(context: TurnDelegationContext) -> None:
    _turn_delegation.set(context)


def get_turn_delegation() -> TurnDelegationContext | None:
    return _turn_delegation.get()


def ensure_subagent_run_buffer() -> None:
    if _subagent_runs.get() is None:
        _subagent_runs.set([])


def append_subagent_run(record: dict[str, Any]) -> None:
    ensure_subagent_run_buffer()
    runs = _subagent_runs.get()
    if runs is None:
        return
    runs.append(record)


def consume_subagent_runs() -> list[dict[str, Any]]:
    runs = _subagent_runs.get()
    if not runs:
        return []
    copied = list(runs)
    runs.clear()
    return copied
