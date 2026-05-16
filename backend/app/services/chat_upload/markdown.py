"""聊天附件上传：Markdown 处理服务。"""

from __future__ import annotations

import asyncio
import hashlib

from fastapi import HTTPException, UploadFile

from app.schemas.chat import MarkdownBlock
from app.services.chat_upload.attachment import (
    MARKDOWN_CONTENT_TYPE,
    build_attachment_preview_url,
    get_user_upload_dir,
    sanitize_upload_display_name,
)
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    index_uploaded_text_chunks,
)
from app.utils.logger import logger

# 仅检测常见纯文本后缀，避免误接二进制文件
_TEXT_MARKDOWN_CONTENT_TYPES = {
    MARKDOWN_CONTENT_TYPE,
    "text/x-markdown",
    "text/plain",
}


def _markdown_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_markdown_block(
    *,
    content_hash: str,
    user_id: str,
    filename: str,
    file_size: int,
    file: UploadFile,
) -> MarkdownBlock:
    display_name = sanitize_upload_display_name(
        file.filename,
        ext=".md",
        default_stem="document",
    )
    url = build_attachment_preview_url(user_id, filename)
    return MarkdownBlock(
        id=content_hash,
        type="markdown",
        url=url,
        name=display_name,
        size=file_size,
        mime="text/markdown",
    )


async def save_chat_markdown(*, user_id: str, file: UploadFile) -> MarkdownBlock:
    """保存上传 Markdown（按内容 SHA-256 命名）；已存在同内容则复用。"""
    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    is_md_ext = raw_filename.endswith(".md") or raw_filename.endswith(".markdown")
    is_md_content_type = content_type in _TEXT_MARKDOWN_CONTENT_TYPES

    if not is_md_ext and not is_md_content_type:
        raise HTTPException(status_code=400, detail="仅支持 Markdown 文件")

    chunk = await file.read(10 * 1024 * 1024 + 1)
    if len(chunk) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Markdown 文件大小不能超过 10MB")

    # 简单校验：文件内容应为合法 UTF-8 文本
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Markdown 文件编码无效，请使用 UTF-8 编码"
        ) from exc

    content_hash = _markdown_sha256_hex(chunk)
    filename = f"{content_hash}.md"
    file_name = sanitize_upload_display_name(
        file.filename,
        ext=".md",
        default_stem="document",
    )

    upload_dir = get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename

    # 去重：文件已存在且内容一致则直接返回
    if dest.is_file():
        existing = await asyncio.to_thread(dest.read_bytes)
        if existing == chunk:
            logger.info(
                "Chat markdown deduplicated",
                user_id=user_id,
                filename=filename,
                bytes=len(existing),
                embedding_skipped=True,
            )
            return _build_markdown_block(
                content_hash=content_hash,
                user_id=user_id,
                filename=filename,
                file_size=len(existing),
                file=file,
            )

    await asyncio.to_thread(dest.write_bytes, chunk)

    # RAG 向量索引
    markdown_text = chunk.decode("utf-8")
    try:
        await index_uploaded_text_chunks(
            user_id=user_id,
            file_id=content_hash,
            text=markdown_text,
            file_name=file_name,
            source_kind="markdown",
            text_format="markdown",
            original_size_bytes=len(chunk),
            processed_size_bytes=len(chunk),
        )
    except KbFileChunkIndexingError as exc:
        logger.error(
            "Chat markdown embedding indexing failed",
            user_id=user_id,
            file_id=content_hash,
            filename=filename,
            error=exc,
        )
        raise HTTPException(
            status_code=502, detail=f"Markdown 分块向量入库失败：{exc}"
        ) from exc

    logger.info(
        "Chat markdown saved",
        user_id=user_id,
        filename=filename,
        bytes=len(chunk),
        deduplicated=False,
    )
    return _build_markdown_block(
        content_hash=content_hash,
        user_id=user_id,
        filename=filename,
        file_size=len(chunk),
        file=file,
    )
