"""Agent skills + sandbox workspace tools MCP server."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.agent_skills import (
    skill_registry,
)
from app.mcp.mcp_servers.agent_skills_mcp.config import (
    MAX_READ_CHARS,
    MAX_SKILL_BODY_CHARS,
    MAX_WORKSPACE_BYTES,
    USER_DATA_ROOT,
)
from app.utils.logger import logger

mcp = FastMCP(name="Agent Skills MCP Service")

_FORBIDDEN_SEGMENTS = {
    ".git",
    ".ssh",
    ".aws",
    ".cursor",
    "__pycache__",
}


def _validate_user_id(user_id: str) -> str:
    normalized = (user_id or "").strip()
    if (
        not normalized
        or "/" in normalized
        or "\\" in normalized
        or ".." in normalized
        or normalized.startswith(".")
    ):
        raise ValueError("invalid user_id")
    return normalized


def _get_workspace_root(user_id: str) -> Path:
    safe_user_id = _validate_user_id(user_id)
    root = (USER_DATA_ROOT / safe_user_id / "workspace").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_workspace_path(user_id: str, relative_path: str) -> tuple[Path, Path]:
    root = _get_workspace_root(user_id)
    relative = (relative_path or "").strip()
    if not relative:
        return root, root
    if Path(relative).is_absolute():
        raise ValueError("absolute path is not allowed")

    normalized_parts = [part for part in Path(relative).parts if part not in ("", ".")]
    if not normalized_parts:
        return root, root
    for part in normalized_parts:
        lowered = part.lower()
        if part == ".." or lowered in _FORBIDDEN_SEGMENTS:
            raise ValueError("forbidden path")

    target = (root / Path(*normalized_parts)).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path escapes workspace")
    return root, target


def _workspace_usage(root: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    if not root.exists():
        return file_count, total_bytes
    for path in root.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
    return file_count, total_bytes


def _ensure_write_quota(root: Path, *, target: Path, content: str) -> None:
    file_count, total_bytes = _workspace_usage(root)
    encoded = content.encode("utf-8")
    new_size = len(encoded)

    old_size = target.stat().st_size if target.exists() and target.is_file() else 0
    next_total_bytes = total_bytes - old_size + new_size
    if next_total_bytes > MAX_WORKSPACE_BYTES:
        raise ValueError(
            f"workspace total bytes exceeds limit {MAX_WORKSPACE_BYTES}, "
            "please delete files first"
        )


def _format_usage(root: Path) -> str:
    file_count, total_bytes = _workspace_usage(root)
    return (
        f"workspace={root}, files={file_count}, "
        f"bytes={total_bytes}/{MAX_WORKSPACE_BYTES}"
    )


@mcp.tool(name="load_skill")
async def load_skill(
    name: str = Field(
        description=(
            "技能名称（技能唯一标识），传入需要加载的 skill name；"
            "具体可用项由服务端注册表与白名单配置决定"
        )
    ),
) -> ToolResult:
    document = skill_registry.load(name)
    body = document.body
    truncated = False
    if len(body) > MAX_SKILL_BODY_CHARS:
        body = body[:MAX_SKILL_BODY_CHARS]
        truncated = True
    content = body + ("\n\n[Truncated by system limit]" if truncated else "")
    logger.info(
        "Agent skill loaded",
        skill_name=name,
        truncated=truncated,
        body_length=len(content),
    )
    return ToolResult(
        content=content,
        structured_content={
            "name": document.manifest.name,
            "description": document.manifest.description,
            "truncated": truncated,
        },
    )


@mcp.tool(name="list_workspace_files")
async def list_workspace_files(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(default="", description="相对 workspace 根目录路径"),
) -> ToolResult:
    root, target = _resolve_workspace_path(user_id, path)
    if not target.exists():
        raise ValueError("path does not exist")
    if not target.is_dir():
        raise ValueError("path is not a directory")

    items: list[dict[str, str | int]] = []
    for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
        items.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
            }
        )
    logger.info(
        "Workspace listed",
        user_id=user_id,
        path=str(target),
        items_count=len(items),
    )
    return ToolResult(
        content=f"Listed {len(items)} items under {target}",
        structured_content={"items": items, "usage": _format_usage(root)},
    )


@mcp.tool(name="read_workspace_file")
async def read_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件路径"),
) -> ToolResult:
    _, target = _resolve_workspace_path(user_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("file does not exist")
    content = target.read_text(encoding="utf-8", errors="replace")
    truncated = False
    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS]
        truncated = True
    logger.info(
        "Workspace file read",
        user_id=user_id,
        path=str(target),
        truncated=truncated,
    )
    return ToolResult(
        content=content + ("\n\n[Truncated by system limit]" if truncated else ""),
        structured_content={
            "path": str(path),
            "truncated": truncated,
            "size": target.stat().st_size,
        },
    )


@mcp.tool(name="write_workspace_file")
async def write_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件路径"),
    content: str = Field(description="要写入的文本内容"),
) -> ToolResult:
    root, target = _resolve_workspace_path(user_id, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _ensure_write_quota(root, target=target, content=content)
    target.write_text(content, encoding="utf-8")
    logger.info(
        "Workspace file written",
        user_id=user_id,
        path=str(target),
        bytes=len(content.encode("utf-8")),
    )
    return ToolResult(
        content=f"Wrote file: {target}",
        structured_content={"path": str(path), "usage": _format_usage(root)},
    )


@mcp.tool(name="delete_workspace_file")
async def delete_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件或目录路径"),
) -> ToolResult:
    root, target = _resolve_workspace_path(user_id, path)
    if not target.exists():
        raise ValueError("path does not exist")
    if target == root:
        raise ValueError("cannot delete workspace root")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    logger.info("Workspace path deleted", user_id=user_id, path=str(target))
    return ToolResult(
        content=f"Deleted path: {target}",
        structured_content={"path": str(path), "usage": _format_usage(root)},
    )


@mcp.tool(name="clear_workspace")
async def clear_workspace(
    user_id: str = Field(description="当前用户ID"),
) -> ToolResult:
    root = _get_workspace_root(user_id)
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    logger.info("Workspace cleared", user_id=user_id, path=str(root))
    return ToolResult(
        content=f"Workspace cleared: {root}",
        structured_content={"usage": _format_usage(root)},
    )
