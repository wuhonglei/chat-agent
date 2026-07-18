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
    allocate_unique_display_name,
    build_attachment_preview_url,
    build_conversation_storage_key,
    build_derived_markdown_storage_key,
    ensure_conversation_owned,
    get_conversation_upload_dir,
    sanitize_upload_display_name,
)
from app.services.chat_upload.mineru_markdown_converter import (
    MinerUMarkdownConversionError,
    MinerUMarkdownConverter,
)
from app.services.chat_upload.token_size import count_attachment_token_size
from app.utils.logger import logger


def _pdf_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_pdf_block(
    *,
    content_hash: str,
    user_id: str,
    pdf_display_name: str,
    pdf_storage_key: str,
    md_storage_key: str,
    pdf_size: int,
    markdown_size: int,
    markdown_token_size: int,
) -> PdfBlock:
    markdown_display_name = f"{Path(pdf_display_name).stem}.md"
    pdf_url = build_attachment_preview_url(user_id, pdf_storage_key)
    markdown_url = build_attachment_preview_url(user_id, md_storage_key)
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
        token_size=markdown_token_size,
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


async def save_chat_pdf(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> PdfBlock:
    """保存上传 PDF 至会话 uploads 目录，并生成 derived Markdown。"""
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    content_type = (file.content_type or "").lower()
    if content_type != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="PDF 大小不能超过 10MB")
    if not chunk.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="PDF 文件无效或已损坏")

    content_hash = _pdf_sha256_hex(chunk)
    pdf_display_name = sanitize_upload_display_name(
        file.filename,
        ext=".pdf",
        default_stem="document",
    )
    pdf_display_name = allocate_unique_display_name(
        user_id, conversation_id, pdf_display_name
    )
    pdf_storage_key = build_conversation_storage_key(conversation_id, pdf_display_name)
    md_storage_key = build_derived_markdown_storage_key(
        conversation_id, pdf_display_name
    )

    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    dest: Path = upload_dir / pdf_display_name
    md_path = upload_dir / "derived" / f"{Path(pdf_display_name).stem}.md"
    images_dir = upload_dir / "derived" / "images"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(dest.write_bytes, chunk)

    converter = MinerUMarkdownConverter()
    try:
        await converter.convert_to_markdown(
            dest, md_path=md_path, images_dir=images_dir
        )
    except MinerUMarkdownConversionError as exc:
        logger.error(
            "Chat pdf markdown conversion failed",
            user_id=user_id,
            storage_key=pdf_storage_key,
            error=exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"MinerU 转换失败：{exc}",
        ) from exc

    try:
        markdown_text = await asyncio.to_thread(md_path.read_text, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Chat pdf markdown read failed after conversion",
            user_id=user_id,
            content_id=content_hash,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(status_code=502, detail="读取 Markdown 文件失败") from exc

    markdown_size = md_path.stat().st_size
    pdf_size = dest.stat().st_size
    markdown_token_size = count_attachment_token_size(markdown_text)

    logger.info(
        "Chat pdf saved",
        user_id=user_id,
        conversation_id=conversation_id,
        storage_key=pdf_storage_key,
        bytes=pdf_size,
        markdown_storage_key=md_storage_key,
        markdown_bytes=markdown_size,
        token_size=markdown_token_size,
    )
    return _build_pdf_block(
        content_hash=content_hash,
        user_id=user_id,
        pdf_display_name=pdf_display_name,
        pdf_storage_key=pdf_storage_key,
        md_storage_key=md_storage_key,
        pdf_size=pdf_size,
        markdown_size=markdown_size,
        markdown_token_size=markdown_token_size,
    )
