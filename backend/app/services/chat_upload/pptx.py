"""聊天附件上传：PowerPoint (.pptx) 处理服务。"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.schemas.chat import MarkdownBlock, PptxBlock
from app.services.chat_upload.attachment import (
    MAX_CHAT_ATTACHMENT_BYTES,
    PPTX_CONTENT_TYPE,
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

# pptx 是 zip 容器，魔数为 PK\x03\x04
_OOXML_MAGIC = b"PK\x03\x04"


def _pptx_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_pptx_block(
    *,
    content_hash: str,
    user_id: str,
    pptx_display_name: str,
    pptx_storage_key: str,
    md_storage_key: str,
    pptx_size: int,
    markdown_size: int,
    markdown_token_size: int,
) -> PptxBlock:
    markdown_display_name = f"{Path(pptx_display_name).stem}.md"
    pptx_url = build_attachment_preview_url(user_id, pptx_storage_key)
    markdown_url = build_attachment_preview_url(user_id, md_storage_key)
    markdown_block = MarkdownBlock(
        id=content_hash,
        type="markdown",
        url=markdown_url,
        storage_key=md_storage_key,
        storage_version=STORAGE_VERSION,
        derived_from_id=content_hash,
        derived_kind="pptx_to_markdown",
        name=markdown_display_name,
        size=markdown_size,
        token_size=markdown_token_size,
        mime="text/markdown",
    )
    return PptxBlock(
        id=content_hash,
        type="pptx",
        url=pptx_url,
        storage_key=pptx_storage_key,
        storage_version=STORAGE_VERSION,
        name=pptx_display_name,
        size=pptx_size,
        mime=PPTX_CONTENT_TYPE,
        markdown=markdown_block,
    )


async def save_chat_pptx(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> PptxBlock:
    """保存上传 PowerPoint (.pptx) 至会话 uploads 目录，并生成 derived Markdown。"""
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    if content_type != PPTX_CONTENT_TYPE and not raw_filename.endswith(".pptx"):
        raise HTTPException(status_code=400, detail="仅支持 .pptx 文件")

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="PowerPoint 大小不能超过 10MB")
    if not chunk.startswith(_OOXML_MAGIC):
        raise HTTPException(status_code=400, detail="PowerPoint 文件无效或已损坏")

    content_hash = _pptx_sha256_hex(chunk)
    pptx_display_name = sanitize_upload_display_name(
        file.filename,
        ext=".pptx",
        default_stem="presentation",
    )
    pptx_display_name = allocate_unique_display_name(
        user_id, conversation_id, pptx_display_name
    )
    pptx_storage_key = build_conversation_storage_key(
        conversation_id, pptx_display_name
    )
    md_storage_key = build_derived_markdown_storage_key(
        conversation_id, pptx_display_name
    )

    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    dest: Path = upload_dir / pptx_display_name
    md_path = upload_dir / "derived" / f"{Path(pptx_display_name).stem}.md"
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
            "Chat pptx markdown conversion failed",
            user_id=user_id,
            storage_key=pptx_storage_key,
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
            "Chat pptx markdown read failed after conversion",
            user_id=user_id,
            content_id=content_hash,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(status_code=502, detail="读取 Markdown 文件失败") from exc

    markdown_size = md_path.stat().st_size
    pptx_size = dest.stat().st_size
    markdown_token_size = count_attachment_token_size(markdown_text)

    logger.info(
        "Chat pptx saved",
        user_id=user_id,
        conversation_id=conversation_id,
        storage_key=pptx_storage_key,
        bytes=pptx_size,
        markdown_storage_key=md_storage_key,
        markdown_bytes=markdown_size,
        token_size=markdown_token_size,
    )
    return _build_pptx_block(
        content_hash=content_hash,
        user_id=user_id,
        pptx_display_name=pptx_display_name,
        pptx_storage_key=pptx_storage_key,
        md_storage_key=md_storage_key,
        pptx_size=pptx_size,
        markdown_size=markdown_size,
        markdown_token_size=markdown_token_size,
    )
