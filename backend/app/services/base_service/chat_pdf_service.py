"""聊天附件上传：PDF 处理服务。"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.schemas.chat import PdfBlock
from app.services.base_service.chat_attachment_service import (
    MAX_CHAT_ATTACHMENT_BYTES,
    PDF_CONTENT_TYPE,
    build_attachment_preview_url,
    get_user_upload_dir,
    sanitize_upload_display_name,
)
from app.utils.common import gen_uuid
from app.utils.logger import logger


async def save_chat_pdf(*, user_id: str, file: UploadFile) -> PdfBlock:
    """保存上传 PDF 并返回 PdfBlock（url 为站内预览路径）。"""
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
    stored_size = len(chunk)
    display_name = sanitize_upload_display_name(
        file.filename,
        ext=".pdf",
        default_stem="document",
    )

    logger.info(
        "Chat pdf saved",
        user_id=user_id,
        filename=filename,
        bytes=stored_size,
    )

    return PdfBlock(
        id=block_id,
        type="pdf",
        url=build_attachment_preview_url(user_id, filename),
        name=display_name,
        size=stored_size,
        mime=PDF_CONTENT_TYPE,
    )
