#!/usr/bin/env python3
"""
为历史消息的 ToolUseBlock 补全 name / server_name / mcp_tool_name 三字段。

背景：MCP 工具名前缀改造后，新消息会在 content_blocks 中持久化 LLM 可见名
（如 tavily_web_search）、server_name、mcp_tool_name（裸名 web_search）。
本脚本扫描 messages 表，将旧格式（仅裸名或缺少字段）迁移为新格式。

前置条件：
  - PostgreSQL 已启动，backend/.env 中 DATABASE__HOST 等配置正确
  - 在 backend 目录下执行

用法：
  # 预览将修改哪些消息（不写库）
  cd backend && uv run python scripts/backfill_tool_use_block_names.py --dry-run

  # 仅校验现有数据是否符合三字段约定（不写库）
  cd backend && uv run python scripts/backfill_tool_use_block_names.py --verify-only

  # 执行迁移并提交
  cd backend && uv run python scripts/backfill_tool_use_block_names.py

  # 从 JSON 快照回滚 content_blocks（JSON 为 [{message_id, content_blocks}, ...]）
  cd backend && uv run python scripts/backfill_tool_use_block_names.py --rollback-from backup.json

建议流程：先 --dry-run 确认影响范围 → 备份数据库或导出快照 → 正式执行 → --verify-only 复核。
输出中的 fallback resolutions 表示裸名无法唯一映射时使用了启发式 server 归属，需人工抽查。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Allow running as `uv run python backend/scripts/backfill_tool_use_block_names.py`
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.mcp.tool_naming import llm_tool_name, resolve_server_by_prefix  # noqa: E402
from app.models.message_db import MessageDb  # noqa: E402

STATIC_BARE_TOOL_TO_SERVER: dict[str, str] = {
    "web_search": "tavily",
    "web_pages_extract": "tavily",
    "web_site_crawl": "tavily",
    "web_site_map": "tavily",
    "research": "tavily",
    "read_file": "file",
    "write_file": "file",
    "write_workspace_file": "file",
    "edit_file": "file",
    "search_files": "file",
    "load_skill": "skill_manager",
    "shell": "shell",
    "execute_code": "code-exec",
    "list_runtimes": "code-exec",
    "resolve-library-id": "context7",
    "query-docs": "context7",
    "get_current_time": "time",
    "search_city": "weather",
    "get_current_weather": "weather",
    "get_weather_hourly_forecast": "weather",
    "get_weather_daily_forecast": "weather",
    "get_weather_alerts": "weather",
}

KNOWN_SERVERS = sorted(
    set(settings.mcp.mcp_servers) | set(STATIC_BARE_TOOL_TO_SERVER.values()),
    key=len,
    reverse=True,
)


def _resolve_bare_name(
    bare_name: str,
    agent_mode: bool,
) -> tuple[str, str, bool]:
    """Return (server_name, llm_name, used_fallback)."""
    preferred = STATIC_BARE_TOOL_TO_SERVER.get(bare_name)
    mode_servers = (
        settings.mcp.agent_mode_servers
        if agent_mode
        else settings.mcp.normal_mode_servers
    )
    enabled = [s for s in mode_servers if s in settings.mcp.mcp_servers]

    if preferred and preferred in settings.mcp.mcp_servers:
        server = preferred
        return server, llm_tool_name(server, bare_name), False

    if enabled:
        server = sorted(enabled)[0]
        return server, llm_tool_name(server, bare_name), True

    server = sorted(settings.mcp.mcp_servers.keys())[0]
    return server, llm_tool_name(server, bare_name), True


def _resolve_prefixed_name(name: str) -> tuple[str, str, str]:
    server = resolve_server_by_prefix(name, KNOWN_SERVERS)
    if not server:
        raise ValueError(f"cannot resolve server for prefixed name: {name!r}")
    prefix = f"{server}_"
    mcp_tool_name = name[len(prefix) :] if name.startswith(prefix) else name
    return name, server, mcp_tool_name


def _infer_agent_mode(conversation_messages: list[MessageDb]) -> bool:
    for msg in conversation_messages:
        blocks = msg.content_blocks or []
        for raw in blocks:
            if not isinstance(raw, dict) or raw.get("type") != "tool_use":
                continue
            name = raw.get("name") or ""
            if name.startswith("file_") or name in ("read_file", "write_file", "shell"):
                return True
            if name.startswith("shell_") or name == "shell":
                return True
    return False


def _process_block(
    block: dict[str, Any],
    agent_mode: bool,
) -> tuple[dict[str, Any], bool, bool]:
    """Return (updated_block, changed, used_fallback)."""
    if block.get("type") != "tool_use":
        return block, False, False
    name = block.get("name")
    if not name:
        return block, False, False

    server_name = block.get("server_name")
    mcp_tool_name = block.get("mcp_tool_name")
    if (
        server_name
        and mcp_tool_name
        and block.get("name") == llm_tool_name(server_name, mcp_tool_name)
    ):
        return block, False, False

    used_fallback = False
    if resolve_server_by_prefix(name, KNOWN_SERVERS):
        llm_name, server_name, mcp_tool_name = _resolve_prefixed_name(name)
    else:
        server_name, llm_name, used_fallback = _resolve_bare_name(name, agent_mode)
        mcp_tool_name = name

    updated = {
        **block,
        "name": llm_name,
        "server_name": server_name,
        "mcp_tool_name": mcp_tool_name,
    }
    return updated, True, used_fallback


def verify_messages(messages: list[MessageDb]) -> list[str]:
    errors: list[str] = []
    for msg in messages:
        if msg.role != "assistant":
            continue
        for raw in msg.content_blocks or []:
            if not isinstance(raw, dict) or raw.get("type") != "tool_use":
                continue
            name = raw.get("name")
            if not name:
                continue
            server_name = raw.get("server_name")
            mcp_tool_name = raw.get("mcp_tool_name")
            if not server_name or not mcp_tool_name:
                errors.append(
                    f"message {msg.id}: block {raw.get('id')} missing server/mcp fields"
                )
                continue
            expected = llm_tool_name(server_name, mcp_tool_name)
            if name != expected:
                errors.append(
                    f"message {msg.id}: block {raw.get('id')} name={name!r} "
                    f"expected {expected!r}"
                )
    return errors


def run_backfill(*, dry_run: bool, verify_only: bool) -> int:
    with Session(engine) as session:
        messages = list(session.exec(select(MessageDb)).all())
        by_conversation: dict[str, list[MessageDb]] = defaultdict(list)
        for msg in messages:
            by_conversation[msg.conversation_id].append(msg)

        changed_count = 0
        fallback_count = 0

        if verify_only:
            errors = verify_messages(messages)
            if errors:
                for err in errors[:50]:
                    print(err)
                print(f"verify failed: {len(errors)} issue(s)")
                return 1
            print("verify passed")
            return 0

        for conv_id, conv_messages in by_conversation.items():
            agent_mode = _infer_agent_mode(conv_messages)
            for msg in conv_messages:
                if msg.role != "assistant" or not msg.content_blocks:
                    continue
                new_blocks: list[Any] = []
                msg_changed = False
                for raw in msg.content_blocks:
                    updated, changed, used_fallback = _process_block(raw, agent_mode)
                    new_blocks.append(updated)
                    if changed:
                        msg_changed = True
                        changed_count += 1
                    if used_fallback:
                        fallback_count += 1
                if msg_changed:
                    if not dry_run:
                        msg.content_blocks = new_blocks
                        session.add(msg)
                    else:
                        print(f"would update message {msg.id} conversation {conv_id}")

        if dry_run:
            print(f"dry-run: would update {changed_count} tool_use block(s)")
            print(f"fallback resolutions: {fallback_count}")
            return 0

        session.commit()
        errors = verify_messages(messages)
        if errors:
            print(f"post-backfill verify failed: {len(errors)} issue(s)")
            return 1
        print(f"backfill complete: updated {changed_count} block(s)")
        print(f"fallback resolutions: {fallback_count}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ToolUseBlock naming fields")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--rollback-from",
        type=Path,
        help="Restore content_blocks snapshots from JSON file",
    )
    args = parser.parse_args()

    if args.rollback_from:
        data = json.loads(args.rollback_from.read_text())
        with Session(engine) as session:
            for entry in data:
                msg = session.get(MessageDb, entry["message_id"])
                if msg:
                    msg.content_blocks = entry["content_blocks"]
                    session.add(msg)
            session.commit()
        print(f"rollback complete: {len(data)} message(s)")
        return

    exit_code = run_backfill(dry_run=args.dry_run, verify_only=args.verify_only)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
