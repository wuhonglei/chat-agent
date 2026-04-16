"""聊天附件上传：PDF 处理服务。"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, UploadFile

from app.schemas.chat import MarkdownBlock, PdfBlock
from app.services.base_service.chat_attachment_service import (
    MAX_CHAT_ATTACHMENT_BYTES,
    PDF_CONTENT_TYPE,
    build_attachment_preview_url,
    get_user_upload_dir,
    sanitize_upload_display_name,
)
from app.services.base_service.pdf_markdown_converter import (
    PdfMarkdownConversionError,
    PdfMarkdownConverter,
)
from app.utils.common import gen_uuid
from app.utils.logger import logger


async def save_chat_pdf(*, user_id: str, file: UploadFile) -> PdfBlock:
    """保存上传 PDF，转换 Markdown，并返回包含 markdownBlock 的 PdfBlock。"""
    content_type = (file.content_type or "").lower()
    if content_type != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    block_id = gen_uuid()
    filename = f"{block_id}.pdf"

    upload_dir = get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="PDF 大小不能超过 10MB")
    if not chunk.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="PDF 文件无效或已损坏")

    dest.write_bytes(chunk)
    md_path = dest.with_suffix(".md")
    converter = PdfMarkdownConverter()
    try:
        markdown = await asyncio.to_thread(converter.convert_pdf_to_markdown, dest)
        await asyncio.to_thread(converter.save_markdown, markdown, md_path)
    except PdfMarkdownConversionError as exc:
        logger.error(
            "Chat pdf markdown conversion failed",
            user_id=user_id,
            filename=filename,
            error=exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"PDF 转 Markdown 失败：{exc}",
        ) from exc

    markdown_size = md_path.stat().st_size
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

    logger.info(
        "Chat pdf saved",
        user_id=user_id,
        filename=filename,
        bytes=len(chunk),
        markdown_filename=md_path.name,
        markdown_bytes=markdown_size,
    )
    pdf_url = build_attachment_preview_url(user_id, filename)
    markdown_url = build_attachment_preview_url(user_id, md_path.name)
    markdown_block = MarkdownBlock(
        id=block_id,
        type="markdown",
        url=markdown_url,
        name=markdown_display_name,
        size=markdown_size,
        mime="text/markdown",
    )
    return PdfBlock(
        id=block_id,
        type="pdf",
        url=pdf_url,
        name=pdf_display_name,
        size=len(chunk),
        mime=PDF_CONTENT_TYPE,
        markdownBlock=markdown_block,
    )
