"""Request-scoped delegation context and audit buffer.

The audit list is created on the parent turn and copied by reference into
tool tasks (``asyncio.ensure_future`` copies the context, not the list).

In-process FastMCP runs ``delegate_task`` on the client session task. That
task copies contextvars when it starts, so a later ``set()`` on the request
task is invisible. ``publish_turn_delegation`` captures the caller task's
snapshot; the tool activates it after the MCP hop.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from app.schemas.config import LLMConfig
from app.utils.context import RequestContext, request_context_var

DELEGATION_TOKEN_META_KEY = "turn_delegation_token"

_turn_delegation: ContextVar[TurnDelegationContext | None] = ContextVar(
    "turn_delegation",
    default=None,
)
_subagent_runs: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "subagent_runs",
    default=None,
)
_activation_stack: ContextVar[tuple[tuple[Token[Any], ...], ...] | None] = ContextVar(
    "subagent_activation_stack",
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


@dataclass(slots=True)
class _PublishedTurn:
    """Caller-task snapshot handed to the FastMCP session task."""

    delegation: TurnDelegationContext
    runs: list[dict[str, Any]]
    request: RequestContext | None


_published: dict[str, _PublishedTurn] = {}


def set_turn_delegation(context: TurnDelegationContext) -> None:
    _turn_delegation.set(context)
    # 标题流会用新任务恢复 async generator。新任务拿不到上一段里的
    # ContextVar.set，但会共享中间件放进请求任务的 RequestContext 对象。
    request = request_context_var.get()
    if request is not None and getattr(request, "_turn_delegation", None) is None:
        request._turn_delegation = context


def get_turn_delegation() -> TurnDelegationContext | None:
    current = _turn_delegation.get()
    if current is not None:
        return current
    request = request_context_var.get()
    if request is None:
        return None
    value = getattr(request, "_turn_delegation", None)
    if isinstance(value, TurnDelegationContext):
        return value
    return None


def reset_turn_delegation() -> None:
    _turn_delegation.set(None)
    request = request_context_var.get()
    if request is not None and hasattr(request, "_turn_delegation"):
        delattr(request, "_turn_delegation")


def delegation_token_from_meta(meta: Any) -> str | None:
    """Read the publish token from an MCP request ``_meta`` payload."""
    if meta is None:
        return None
    value: Any
    if isinstance(meta, dict):
        value = meta.get(DELEGATION_TOKEN_META_KEY)
    else:
        value = getattr(meta, DELEGATION_TOKEN_META_KEY, None)
        if value is None and hasattr(meta, "model_dump"):
            dumped = meta.model_dump()
            if isinstance(dumped, dict):
                value = dumped.get(DELEGATION_TOKEN_META_KEY)
    if isinstance(value, str) and value:
        return value
    return None


def publish_turn_delegation() -> str | None:
    """Stash the current task's turn snapshot and return a lookup token."""
    parent = _turn_delegation.get()
    if parent is None:
        return None
    runs = _subagent_runs.get()
    if runs is None:
        runs = []
        _subagent_runs.set(runs)
    token = uuid.uuid4().hex
    _published[token] = _PublishedTurn(
        delegation=parent,
        runs=runs,
        request=request_context_var.get(),
    )
    return token


def _push_activation(tokens: list[Token[Any]]) -> None:
    stack = _activation_stack.get()
    frame = tuple(tokens)
    _activation_stack.set((frame,) if stack is None else (*stack, frame))


def activate_published_turn(token: str) -> bool:
    """Install a published snapshot into the current task's context."""
    published = _published.get(token)
    if published is None:
        return False
    tokens: list[Token[Any]] = [
        _turn_delegation.set(published.delegation),
        _subagent_runs.set(published.runs),
    ]
    if published.request is not None:
        tokens.append(request_context_var.set(published.request))
    _push_activation(tokens)
    return True


def isolate_turn_delegation() -> None:
    """Hide any snapshot already bound to this task for the current call."""
    _push_activation(
        [
            _turn_delegation.set(None),
            _subagent_runs.set(None),
        ]
    )


def release_published_turn(token: str) -> None:
    _published.pop(token, None)


def clear_server_task_delegation() -> None:
    """Restore contextvars to the values from before this call's activation.

    ``Token.reset`` only affects the current task, so the parent turn keeps
    its own snapshot. Nested ``delegate_task`` calls pop one frame each.
    """
    stack = _activation_stack.get()
    if not stack:
        return
    for token in reversed(stack[-1]):
        token.var.reset(token)
    _activation_stack.set(None if len(stack) == 1 else stack[:-1])


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
