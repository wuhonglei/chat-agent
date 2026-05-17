"""聊天附件上传：PDF 处理服务。"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.schemas.chat import MarkdownBlock, PdfBlock
from app.services.chat_upload.attachment import (
    MAX_CHAT_ATTACHMENT_BYTES,
    PDF_CONTENT_TYPE,
    STORAGE_VERSION,
    build_attachment_preview_url,
    build_derived_markdown_storage_key,
    build_raw_storage_key,
    mount_conversation_attachment,
    sanitize_upload_display_name,
    upsert_attachment_file,
)
from app.services.chat_upload.attachment import (
    get_user_shared_upload_dir as _get_user_shared_upload_dir,
)
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    index_uploaded_text_chunks,
)
from app.services.chat_upload.pdf_markdown_converter import (
    PdfMarkdownConversionError,
    PdfMarkdownConverter,
)
from app.utils.logger import logger


def _pdf_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_user_upload_dir(user_id: str) -> Path:
    """Compatibility hook for tests; production path is shared/uploads."""
    return _get_user_shared_upload_dir(user_id)


def _build_pdf_block(
    *,
    content_hash: str,
    user_id: str,
    pdf_storage_key: str,
    md_storage_key: str,
    pdf_size: int,
    markdown_size: int,
    file: UploadFile,
    db: Session | None = None,
    conversation_id: str | None = None,
) -> PdfBlock:
    pdf_display_name = sanitize_upload_display_name(
        file.filename,
        ext=".pdf",
        default_stem="document",
    )
    markdown_display_name = sanitize_upload_display_name(
        file.filename,
        ext=".md",
        default_stem="document",
    )
    pdf_url = build_attachment_preview_url(user_id, pdf_storage_key)
    markdown_url = build_attachment_preview_url(user_id, md_storage_key)
    pdf_file = upsert_attachment_file(
        db=db,
        user_id=user_id,
        content_id=content_hash,
        storage_key=pdf_storage_key,
        kind="raw",
        mime=PDF_CONTENT_TYPE,
        size=pdf_size,
        display_name=pdf_display_name,
    )
    md_file = upsert_attachment_file(
        db=db,
        user_id=user_id,
        content_id=content_hash,
        storage_key=md_storage_key,
        kind="derived",
        mime="text/markdown",
        size=markdown_size,
        display_name=markdown_display_name,
        derived_from_id=content_hash,
        derived_kind="pdf_to_markdown",
    )
    mount_conversation_attachment(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        attachment_file=pdf_file,
    )
    mount_conversation_attachment(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        attachment_file=md_file,
    )
    markdown_block = MarkdownBlock(
        id=content_hash,
        type="markdown",
        url=markdown_url,
        storage_key=md_storage_key,
        storage_version=STORAGE_VERSION,
        derived_from_id=content_hash,
        derived_kind="pdf_to_markdown",
        name=markdown_display_name,
        size=markdown_size,
        mime="text/markdown",
    )
    return PdfBlock(
        id=content_hash,
        type="pdf",
        url=pdf_url,
        storage_key=pdf_storage_key,
        storage_version=STORAGE_VERSION,
        name=pdf_display_name,
        size=pdf_size,
        mime=PDF_CONTENT_TYPE,
        markdown=markdown_block,
    )


async def _index_pdf_markdown_or_raise(
    *,
    user_id: str,
    file_id: str,
    md_path: Path,
    file_name: str,
    original_size_bytes: int,
    processed_size_bytes: int,
) -> None:
    try:
        markdown_text = await asyncio.to_thread(md_path.read_text, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Chat pdf markdown read failed before embedding",
            user_id=user_id,
            file_id=file_id,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(status_code=502, detail="读取 Markdown 文件失败") from exc

    try:
        await index_uploaded_text_chunks(
            user_id=user_id,
            file_id=file_id,
            text=markdown_text,
            file_name=file_name,
            source_kind="pdf",
            text_format="markdown",
            original_size_bytes=original_size_bytes,
            processed_size_bytes=processed_size_bytes,
        )
    except KbFileChunkIndexingError as exc:
        logger.error(
            "Chat pdf embedding indexing failed",
            user_id=user_id,
            file_id=file_id,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(
            status_code=502, detail=f"PDF 分块向量入库失败：{exc}"
        ) from exc


async def save_chat_pdf(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str | None = None,
    db: Session | None = None,
) -> PdfBlock:
    """保存上传 PDF（按内容 SHA-256 命名）；已存在同内容则复用并返回既有结果。"""
    content_type = (file.content_type or "").lower()
    if content_type != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="PDF 大小不能超过 10MB")
    if not chunk.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="PDF 文件无效或已损坏")

    content_hash = _pdf_sha256_hex(chunk)
    pdf_storage_key = build_raw_storage_key(content_hash, ".pdf")
    md_storage_key = build_derived_markdown_storage_key(content_hash)
    file_name = sanitize_upload_display_name(
        file.filename,
        ext=".pdf",
        default_stem="document",
    )

    upload_dir = get_user_upload_dir(user_id)
    dest: Path = upload_dir / pdf_storage_key
    md_path = upload_dir / md_storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    if dest.is_file() and md_path.is_file():
        if dest.stat().st_size == len(chunk):
            existing_pdf = await asyncio.to_thread(dest.read_bytes)
            if existing_pdf == chunk:
                markdown_size = md_path.stat().st_size
                logger.info(
                    "Chat pdf deduplicated",
                    user_id=user_id,
                    storage_key=pdf_storage_key,
                    pdf_bytes=len(existing_pdf),
                    markdown_bytes=markdown_size,
                    embedding_skipped=True,
                )
                return _build_pdf_block(
                    content_hash=content_hash,
                    user_id=user_id,
                    pdf_storage_key=pdf_storage_key,
                    md_storage_key=md_storage_key,
                    pdf_size=len(existing_pdf),
                    markdown_size=markdown_size,
                    file=file,
                    db=db,
                    conversation_id=conversation_id,
                )

    wrote_pdf = False
    if not dest.is_file():
        await asyncio.to_thread(dest.write_bytes, chunk)
        wrote_pdf = True
    else:
        existing_pdf = await asyncio.to_thread(dest.read_bytes)
        if existing_pdf != chunk:
            await asyncio.to_thread(dest.write_bytes, chunk)
            wrote_pdf = True

    if wrote_pdf and md_path.is_file():
        await asyncio.to_thread(md_path.unlink)

    if wrote_pdf or not md_path.is_file():
        converter = PdfMarkdownConverter()
        try:
            markdown = await asyncio.to_thread(converter.convert_pdf_to_markdown, dest)
            await asyncio.to_thread(converter.save_markdown, markdown, md_path)
        except PdfMarkdownConversionError as exc:
            logger.error(
                "Chat pdf markdown conversion failed",
                user_id=user_id,
                storage_key=pdf_storage_key,
                error=exc,
            )
            raise HTTPException(
                status_code=502,
                detail=f"PDF 转 Markdown 失败：{exc}",
            ) from exc

    markdown_size = md_path.stat().st_size
    pdf_size = dest.stat().st_size
    await _index_pdf_markdown_or_raise(
        user_id=user_id,
        file_id=content_hash,
        md_path=md_path,
        file_name=file_name,
        original_size_bytes=pdf_size,
        processed_size_bytes=markdown_size,
    )

    logger.info(
        "Chat pdf saved",
        user_id=user_id,
        storage_key=pdf_storage_key,
        bytes=pdf_size,
        markdown_storage_key=md_storage_key,
        markdown_bytes=markdown_size,
        deduplicated=False,
    )
    return _build_pdf_block(
        content_hash=content_hash,
        user_id=user_id,
        pdf_storage_key=pdf_storage_key,
        md_storage_key=md_storage_key,
        pdf_size=pdf_size,
        markdown_size=markdown_size,
        file=file,
        db=db,
        conversation_id=conversation_id,
    )
