"""聊天附件上传：Markdown 处理服务。"""

from __future__ import annotations

import asyncio
import hashlib

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.schemas.chat import MarkdownBlock
from app.services.chat_upload.attachment import (
    MARKDOWN_CONTENT_TYPE,
    STORAGE_VERSION,
    allocate_unique_display_name,
    build_attachment_preview_url,
    build_conversation_storage_key,
    ensure_conversation_owned,
    get_conversation_upload_dir,
    sanitize_upload_display_name,
)
from app.services.chat_upload.token_size import (
    count_attachment_lines,
    count_attachment_token_size,
)
from app.utils.logger import logger

_TEXT_MARKDOWN_CONTENT_TYPES = {
    MARKDOWN_CONTENT_TYPE,
    "text/x-markdown",
    "text/plain",
}


def _markdown_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def save_chat_markdown(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> MarkdownBlock:
    """保存上传 Markdown 至会话 uploads 目录。"""
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    is_md_ext = raw_filename.endswith(".md") or raw_filename.endswith(".markdown")
    is_md_content_type = content_type in _TEXT_MARKDOWN_CONTENT_TYPES

    if not is_md_ext and not is_md_content_type:
        raise HTTPException(status_code=400, detail="仅支持 Markdown 文件")

    chunk = await file.read(10 * 1024 * 1024 + 1)
    if len(chunk) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Markdown 文件大小不能超过 10MB")

    try:
        markdown_text = chunk.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Markdown 文件编码无效，请使用 UTF-8 编码"
        ) from exc

    content_hash = _markdown_sha256_hex(chunk)
    display_name = sanitize_upload_display_name(
        file.filename,
        ext=".md",
        default_stem="document",
    )
    display_name = allocate_unique_display_name(user_id, conversation_id, display_name)
    storage_key = build_conversation_storage_key(conversation_id, display_name)

    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    dest = upload_dir / display_name
    await asyncio.to_thread(dest.write_bytes, chunk)

    token_size = count_attachment_token_size(markdown_text)
    lines_count = count_attachment_lines(markdown_text)

    logger.info(
        "Chat markdown saved",
        user_id=user_id,
        conversation_id=conversation_id,
        storage_key=storage_key,
        bytes=len(chunk),
        token_size=token_size,
        lines_count=lines_count,
    )
    url = build_attachment_preview_url(user_id, storage_key)
    return MarkdownBlock(
        id=content_hash,
        type="markdown",
        url=url,
        storage_key=storage_key,
        storage_version=STORAGE_VERSION,
        name=display_name,
        size=len(chunk),
        token_size=token_size,
        lines_count=lines_count,
        mime="text/markdown",
    )
