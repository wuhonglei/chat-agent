"""User data read-only APIs for project preview."""

from __future__ import annotations

import base64
import io
import mimetypes
import os
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.utils.auth_deps import get_auth_token_info
from app.utils.logger import logger
from app.utils.workspace import resolve_conversation_path

router = APIRouter()

_HEAVY_DIR_NAMES = {
    "node_modules",
    ".next",
    ".git",
    ".turbo",
    ".cache",
    ".local",
    "Library",
    ".vite-plus",
    ".DS_Store",
}

_PREVIEW_ENTRY_CANDIDATES = (
    "workspace/dist/index.html",
    "workspace/build/index.html",
    "dist/index.html",
    "build/index.html",
)
_PREVIEW_ASSET_PATTERN = re.compile(
    r'(?P<prefix>\b(?:src|href)\s*=\s*["\'])(?P<path>/assets/[^"\']+)(?P<suffix>["\'])'
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
    conversation_root: Path,
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
        relative_path = child.relative_to(conversation_root).as_posix()
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


def _resolve_preview_entry(conversation_root: Path) -> tuple[str, Path] | None:
    for relative_path in _PREVIEW_ENTRY_CANDIDATES:
        candidate = (conversation_root / relative_path).resolve()
        if not str(candidate).startswith(str(conversation_root)):
            continue
        if candidate.is_file():
            return relative_path, candidate
    return None


def _inline_preview_assets(html_content: str, entry_file: Path) -> str:
    if "/assets/" not in html_content:
        return html_content

    dist_root = entry_file.parent.resolve()
    cache: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        raw_path = match.group("path")
        suffix = match.group("suffix")
        if raw_path in cache:
            return f"{prefix}{cache[raw_path]}{suffix}"

        parsed_path = urlsplit(raw_path).path.lstrip("/")
        asset_file = (dist_root / parsed_path).resolve()
        if not asset_file.is_relative_to(dist_root) or not asset_file.is_file():
            return match.group(0)

        mime_type = (
            mimetypes.guess_type(asset_file.name)[0] or "application/octet-stream"
        )
        encoded = base64.b64encode(asset_file.read_bytes()).decode("ascii")
        data_uri = f"data:{mime_type};base64,{encoded}"
        cache[raw_path] = data_uri
        return f"{prefix}{data_uri}{suffix}"

    return _PREVIEW_ASSET_PATTERN.sub(_replace, html_content)


def _iter_conversation_files(
    conversation_root: Path, *, include_ignored: bool
) -> Iterator[tuple[Path, str]]:
    for current_root, dir_names, file_names in os.walk(conversation_root):
        if not include_ignored:
            dir_names[:] = [
                dir_name
                for dir_name in dir_names
                if not _is_ignored_dir(dir_name, include_ignored=include_ignored)
            ]
        for file_name in file_names:
            file_path = Path(current_root) / file_name
            arc_name = file_path.relative_to(conversation_root).as_posix()
            yield file_path, arc_name


@router.get("/{conversation_id}/files")
async def get_workspace_files(
    conversation_id: str,
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
        root, target = resolve_conversation_path(
            auth_info.user_id, conversation_id, path
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")

    tree_data = _build_tree_data(
        target,
        conversation_root=root,
        include_ignored=include_ignored,
    )
    updated_at = _iso_from_timestamp(root.stat().st_mtime) if root.exists() else None
    return ApiResponse.success(
        data={
            "workspaceId": conversation_id,
            "path": path,
            "treeData": tree_data,
            "updatedAt": updated_at,
        },
        msg="获取文件树成功",
    )


@router.get("/{conversation_id}/file")
async def get_workspace_file(
    conversation_id: str,
    path: str = Query(..., min_length=1),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> FileResponse:
    try:
        _, target = resolve_conversation_path(auth_info.user_id, conversation_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(
        path=str(target),
        media_type=mime_type,
        filename=target.name,
    )


@router.get("/{conversation_id}/download")
async def download_workspace(
    conversation_id: str,
    include_ignored: bool = Query(default=False),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> StreamingResponse:
    try:
        conversation_root, _ = resolve_conversation_path(
            auth_info.user_id, conversation_id, ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not conversation_root.exists() or not conversation_root.is_dir():
        raise HTTPException(status_code=404, detail="会话目录不存在")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(
        zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        has_files = False
        for file_path, arc_name in _iter_conversation_files(
            conversation_root, include_ignored=include_ignored
        ):
            zip_file.write(file_path, arcname=arc_name)
            has_files = True
        if not has_files:
            zip_file.writestr("README.txt", "Workspace is empty.\n")
    zip_buffer.seek(0)

    filename = f"{conversation_id}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{user_id}/{conversation_id}/preview-content")
async def get_workspace_preview_content(
    user_id: str,
    conversation_id: str,
) -> HTMLResponse:
    try:
        conversation_root, _ = resolve_conversation_path(user_id, conversation_id, "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info(f"conversation_root: {conversation_root}")
    entry = _resolve_preview_entry(conversation_root)
    logger.info(f"entry: {entry}")
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="未找到可预览入口文件，请先构建项目",
        )

    path, target = entry
    if _is_probably_binary(target):
        raise HTTPException(status_code=400, detail="预览入口文件不可为二进制内容")

    content = target.read_text(encoding="utf-8", errors="replace")
    content = _inline_preview_assets(content, target)
    return HTMLResponse(
        content=content,
        headers={
            "X-Workspace-Preview-Path": path,
        },
    )
