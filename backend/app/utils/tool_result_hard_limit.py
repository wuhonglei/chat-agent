"""工具结果硬上限：按 agent_mode 落盘预览或头尾截断，并做同轮聚合预算。"""

from __future__ import annotations

from pathlib import Path

from app.mcp.constants import (
    CODE_SERVER,
    CONTEXT7_SERVER,
    FILE_SERVER,
    SHELL_SERVER,
    SKILL_MANAGER_SERVER,
    TAVILY_SERVER,
    TIME_SERVER,
    WEATHER_SERVER,
    ZREAD_SERVER,
)
from app.mcp.tool_naming import bare_tool_name
from app.schemas.config import ToolResultHardLimitConfig
from app.schemas.llm import ToolResultMessage
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths

_KNOWN_MCP_SERVERS = (
    TAVILY_SERVER,
    FILE_SERVER,
    SKILL_MANAGER_SERVER,
    SHELL_SERVER,
    CODE_SERVER,
    WEATHER_SERVER,
    TIME_SERVER,
    CONTEXT7_SERVER,
    ZREAD_SERVER,
)

_PERSISTED_MARKER = "full output persisted"
_TRUNCATED_MARKER = "内容已截断"


def extract_bare_tool_name(tool_name: str) -> str:
    """Resolve bare MCP tool name from an LLM-visible tool name."""
    return bare_tool_name(tool_name, _KNOWN_MCP_SERVERS)


def resolve_max_chars(tool_name: str, config: ToolResultHardLimitConfig) -> int | None:
    """Return effective per-tool char threshold; None means Layer-2 skip."""
    bare = extract_bare_tool_name(tool_name)
    if tool_name in config.tool_overrides:
        value = config.tool_overrides[tool_name]
    elif bare in config.tool_overrides:
        value = config.tool_overrides[bare]
    else:
        value = config.max_chars
    if value == 0:
        return None
    return value


def is_hard_limited(content: str) -> bool:
    """Whether content already went through persist/truncate replacement."""
    return _PERSISTED_MARKER in content or _TRUNCATED_MARKER in content


def _is_budget_exempt(tool_name: str, config: ToolResultHardLimitConfig) -> bool:
    """Whether tool is fully exempt from hard limit (including force / turn budget)."""
    bare = extract_bare_tool_name(tool_name)
    exempt = set(config.exempt_bare_names)
    return bare in exempt or tool_name in exempt


def _count_lines(content: str) -> int:
    """Return line count for tool-output previews (empty content → 0)."""
    if not content:
        return 0
    return len(content.splitlines())


def _build_head_tail_preview(
    content: str, *, head_chars: int, tail_chars: int
) -> tuple[str, str, str]:
    total = len(content)
    if total == 0:
        return "", "", ""
    head_n = min(head_chars, total)
    tail_n = min(tail_chars, max(0, total - head_n))
    head = content[:head_n]
    tail = content[-tail_n:] if tail_n else ""
    return head, tail, content


def _format_truncated_content(
    content: str,
    *,
    head_chars: int,
    tail_chars: int,
) -> str:
    head, tail, _ = _build_head_tail_preview(
        content, head_chars=head_chars, tail_chars=tail_chars
    )
    total = len(content)
    total_lines = _count_lines(content)
    omitted = max(0, total - len(head) - len(tail))
    middle = (
        f"\n\n... [{total} chars total, {total_lines} lines, "
        f"{omitted} omitted, {_TRUNCATED_MARKER}] ...\n\n"
    )
    footer = f"\n\n[{_TRUNCATED_MARKER}，无法回读完整原文]"
    if not tail:
        return head + middle.rstrip() + footer
    return head + middle + tail + footer


def _format_persisted_content(
    content: str,
    *,
    virtual_path: str,
    head_chars: int,
    tail_chars: int,
) -> str:
    head, tail, _ = _build_head_tail_preview(
        content, head_chars=head_chars, tail_chars=tail_chars
    )
    total = len(content)
    total_lines = _count_lines(content)
    middle = (
        f"\n\n... [{total} chars total, {total_lines} lines, "
        f"{_PERSISTED_MARKER}] ...\n\n"
    )
    footer = (
        f"\n\n[完整输出已保存到 {virtual_path}]\n"
        "需要更多细节时请用 read_file 读取该路径（可用 offset/limit）。"
    )
    if not tail:
        return head + middle.rstrip() + footer
    return head + middle + tail + footer


def _persist_content(
    content: str,
    *,
    tool_call_id: str,
    user_id: str,
    conversation_id: str,
    config: ToolResultHardLimitConfig,
) -> str:
    paths = get_paths()
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)
    subdir = (config.persist_subdir or ".tool-results").strip().strip("/")
    persist_dir = workspace / subdir
    persist_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in tool_call_id)
    file_name = f"{safe_id}.txt"
    physical_path: Path = persist_dir / file_name
    physical_path.write_text(content, encoding="utf-8")
    virtual_path = f"{vfs_config.workspace_prefix.rstrip('/')}/{subdir}/{file_name}"
    return virtual_path


def apply_hard_limit(
    message: ToolResultMessage,
    *,
    tool_name: str,
    agent_mode: int,
    user_id: str | None,
    conversation_id: str | None,
    config: ToolResultHardLimitConfig,
    force: bool = False,
) -> ToolResultMessage:
    """Apply per-result hard limit. ``force`` ignores override=0 and max_chars."""
    if not config.enabled:
        return message

    content = message.content or ""
    if not content:
        return message
    if is_hard_limited(content):
        return message

    if _is_budget_exempt(tool_name, config):
        return message

    if not force:
        max_chars = resolve_max_chars(tool_name, config)
        if max_chars is None:
            return message
        if len(content) <= max_chars:
            return message

    can_persist = agent_mode > 0 and bool(user_id) and bool(conversation_id)

    if can_persist:
        try:
            virtual_path = _persist_content(
                content,
                tool_call_id=message.tool_call_id,
                user_id=user_id or "",
                conversation_id=conversation_id or "",
                config=config,
            )
            new_content = _format_persisted_content(
                content,
                virtual_path=virtual_path,
                head_chars=config.preview_head_chars,
                tail_chars=config.preview_tail_chars,
            )
            logger.info(
                "Tool result persisted due to hard limit",
                tool_name=tool_name,
                tool_call_id=message.tool_call_id,
                original_chars=len(content),
                virtual_path=virtual_path,
                force=force,
            )
            return message.model_copy(update={"content": new_content})
        except Exception as exc:
            logger.warning(
                "Tool result persist failed, falling back to truncate",
                tool_name=tool_name,
                tool_call_id=message.tool_call_id,
                error=exc,
                error_type=type(exc).__name__,
            )

    new_content = _format_truncated_content(
        content,
        head_chars=config.preview_head_chars,
        tail_chars=config.preview_tail_chars,
    )
    logger.info(
        "Tool result truncated due to hard limit",
        tool_name=tool_name,
        tool_call_id=message.tool_call_id,
        original_chars=len(content),
        agent_mode=agent_mode,
        force=force,
    )
    return message.model_copy(update={"content": new_content})


def enforce_turn_budget(
    messages: list[ToolResultMessage],
    *,
    tool_name_by_call_id: dict[str, str],
    agent_mode: int,
    user_id: str | None,
    conversation_id: str | None,
    config: ToolResultHardLimitConfig,
) -> list[ToolResultMessage]:
    """Shrink largest results until total content chars fit turn budget."""
    if not config.enabled or config.turn_budget_chars <= 0 or not messages:
        return messages

    updated = list(messages)

    def _total_chars() -> int:
        return sum(len(m.content or "") for m in updated)

    if _total_chars() <= config.turn_budget_chars:
        return updated

    ranked = sorted(
        range(len(updated)),
        key=lambda i: len(updated[i].content or ""),
        reverse=True,
    )
    for idx in ranked:
        if _total_chars() <= config.turn_budget_chars:
            break
        msg = updated[idx]
        if is_hard_limited(msg.content or ""):
            continue
        tool_name = tool_name_by_call_id.get(msg.tool_call_id, "")
        updated[idx] = apply_hard_limit(
            msg,
            tool_name=tool_name,
            agent_mode=agent_mode,
            user_id=user_id,
            conversation_id=conversation_id,
            config=config,
            force=True,
        )

    return updated
