"""Workspace read-only APIs for project preview."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.mcp.mcp_servers.agent_skills_mcp.utils import resolve_workspace_path
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()

_HEAVY_DIR_NAMES = {
    "node_modules",
    ".next",
    ".git",
    "dist",
    "build",
    ".turbo",
    ".cache",
}

_PREVIEW_ENTRY_CANDIDATES = (
    "dist/index.html",
    "build/index.html",
)


def _iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _is_probably_binary(path: Path) -> bool:
    with path.open("rb") as f:
        chunk = f.read(4096)
    if not chunk:
        return False
    return b"\x00" in chunk


def _is_ignored_dir(name: str, *, include_ignored: bool) -> bool:
    return (not include_ignored) and name in _HEAVY_DIR_NAMES


def _has_visible_children(dir_path: Path, *, include_ignored: bool) -> bool:
    for child in dir_path.iterdir():
        if child.is_dir() and _is_ignored_dir(
            child.name, include_ignored=include_ignored
        ):
            continue
        return True
    return False


def _build_tree_data(
    target_root: Path,
    *,
    workspace_root: Path,
    include_ignored: bool,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for child in sorted(
        target_root.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
    ):
        if child.is_dir() and _is_ignored_dir(
            child.name, include_ignored=include_ignored
        ):
            continue
        relative_path = child.relative_to(workspace_root).as_posix()
        if child.is_dir():
            nodes.append(
                {
                    "title": child.name,
                    "path": relative_path,
                    "nodeType": "dir",
                    "hasChildren": _has_visible_children(
                        child, include_ignored=include_ignored
                    ),
                    "children": [],
                }
            )
            continue

        nodes.append(
            {
                "title": child.name,
                "path": relative_path,
                "nodeType": "file",
            }
        )
    return nodes


def _resolve_preview_entry(workspace_root: Path) -> tuple[str, Path] | None:
    for relative_path in _PREVIEW_ENTRY_CANDIDATES:
        candidate = (workspace_root / relative_path).resolve()
        if not str(candidate).startswith(str(workspace_root)):
            continue
        if candidate.is_file():
            return relative_path, candidate
    return None


@router.get("/{workspace_id}/files")
async def get_workspace_files(
    workspace_id: str,
    path: str = Query(default=""),
    depth: int = Query(default=1, ge=1, le=1),
    include_ignored: bool = Query(default=False),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[dict[str, Any]]:
    if depth != 1:
        raise HTTPException(
            status_code=400,
            detail="当前接口仅支持 depth=1，请通过 path 参数懒加载子目录",
        )
    try:
        root, target = resolve_workspace_path(auth_info.user_id, workspace_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")

    tree_data = _build_tree_data(
        target,
        workspace_root=root,
        include_ignored=include_ignored,
    )
    updated_at = _iso_from_timestamp(root.stat().st_mtime) if root.exists() else None
    return ApiResponse.success(
        data={
            "workspaceId": workspace_id,
            "path": path,
            "treeData": tree_data,
            "updatedAt": updated_at,
        },
        msg="获取文件树成功",
    )


@router.get("/{workspace_id}/file-content")
async def get_workspace_file_content(
    workspace_id: str,
    path: str = Query(..., min_length=1),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[dict[str, Any]]:
    try:
        _, target = resolve_workspace_path(auth_info.user_id, workspace_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if _is_probably_binary(target):
        raise HTTPException(status_code=400, detail="暂不支持预览二进制文件")

    content = target.read_text(encoding="utf-8", errors="replace")
    stat = target.stat()
    return ApiResponse.success(
        data={
            "path": path,
            "content": content,
            "size": stat.st_size,
            "updatedAt": _iso_from_timestamp(stat.st_mtime),
        },
        msg="获取文件内容成功",
    )


@router.get("/{workspace_id}/preview-content")
async def get_workspace_preview_content(
    workspace_id: str,
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> HTMLResponse:
    try:
        workspace_root, _ = resolve_workspace_path(auth_info.user_id, workspace_id, "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    entry = _resolve_preview_entry(workspace_root)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="未找到可预览入口文件，请先构建项目",
        )

    path, target = entry
    if _is_probably_binary(target):
        raise HTTPException(status_code=400, detail="预览入口文件不可为二进制内容")

    content = target.read_text(encoding="utf-8", errors="replace")
    return HTMLResponse(
        content=content,
        headers={
            "X-Workspace-Preview-Path": path,
        },
    )
