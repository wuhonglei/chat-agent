"""聊天附件上传：纯文本 / 代码文件处理服务（不转 Markdown）。"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.schemas.chat import TextFileBlock
from app.services.chat_upload.attachment import (
    MAX_CHAT_ATTACHMENT_BYTES,
    STORAGE_VERSION,
    TEXT_FILE_EXTENSIONS,
    allocate_unique_display_name,
    build_attachment_preview_url,
    build_conversation_storage_key,
    ensure_conversation_owned,
    get_conversation_upload_dir,
    media_type_for_preview,
    sanitize_upload_display_name,
)
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    index_uploaded_text_chunks,
)
from app.utils.logger import logger


def _text_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_text_extension(raw_filename: str) -> str:
    """从原始文件名解析受支持的扩展名（小写，带点），否则报错。"""
    ext = Path(raw_filename).suffix.lower()
    if ext not in TEXT_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文本文件类型")
    return ext


async def save_chat_text(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> TextFileBlock:
    """保存上传的纯文本 / 代码文件至会话 uploads 目录，并按纯文本入向量库。"""
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    raw_filename = (file.filename or "").lower()
    ext = _resolve_text_extension(raw_filename)

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    try:
        text = chunk.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="文件编码无效，请使用 UTF-8 编码"
        ) from exc

    content_hash = _text_sha256_hex(chunk)
    display_name = sanitize_upload_display_name(
        file.filename,
        ext=ext,
        default_stem="file",
    )
    display_name = allocate_unique_display_name(user_id, conversation_id, display_name)
    storage_key = build_conversation_storage_key(conversation_id, display_name)

    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    dest = upload_dir / display_name
    await asyncio.to_thread(dest.write_bytes, chunk)

    try:
        await index_uploaded_text_chunks(
            user_id=user_id,
            content_id=content_hash,
            text=text,
            file_name=display_name,
            source_kind="text",
            text_format="text",
            original_size_bytes=len(chunk),
            processed_size_bytes=len(chunk),
        )
    except KbFileChunkIndexingError as exc:
        logger.error(
            "Chat text embedding indexing failed",
            user_id=user_id,
            content_id=content_hash,
            storage_key=storage_key,
            error=exc,
        )
        raise HTTPException(
            status_code=502, detail=f"文本分块向量入库失败：{exc}"
        ) from exc

    logger.info(
        "Chat text file saved",
        user_id=user_id,
        conversation_id=conversation_id,
        storage_key=storage_key,
        bytes=len(chunk),
    )
    url = build_attachment_preview_url(user_id, storage_key)
    return TextFileBlock(
        id=content_hash,
        type="text_file",
        url=url,
        storage_key=storage_key,
        storage_version=STORAGE_VERSION,
        name=display_name,
        size=len(chunk),
        mime=media_type_for_preview(display_name),
    )
