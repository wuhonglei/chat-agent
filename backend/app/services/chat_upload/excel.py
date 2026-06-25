"""聊天附件上传：Excel (.xlsx) 处理服务。"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.schemas.chat import ExcelBlock, MarkdownBlock
from app.services.chat_upload.attachment import (
    EXCEL_CONTENT_TYPE,
    MAX_CHAT_ATTACHMENT_BYTES,
    STORAGE_VERSION,
    allocate_unique_display_name,
    build_attachment_preview_url,
    build_conversation_storage_key,
    build_derived_markdown_storage_key,
    ensure_conversation_owned,
    get_conversation_upload_dir,
    sanitize_upload_display_name,
)
from app.services.chat_upload.excel_markdown_converter import (
    ExcelMarkdownConversionError,
    ExcelMarkdownConverter,
)
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    index_uploaded_text_chunks,
)
from app.utils.logger import logger

# xlsx 是 zip 容器，魔数为 PK\x03\x04
_XLSX_MAGIC = b"PK\x03\x04"


def _excel_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_excel_block(
    *,
    content_hash: str,
    user_id: str,
    excel_display_name: str,
    excel_storage_key: str,
    md_storage_key: str,
    excel_size: int,
    markdown_size: int,
) -> ExcelBlock:
    markdown_display_name = f"{Path(excel_display_name).stem}.md"
    excel_url = build_attachment_preview_url(user_id, excel_storage_key)
    markdown_url = build_attachment_preview_url(user_id, md_storage_key)
    markdown_block = MarkdownBlock(
        id=content_hash,
        type="markdown",
        url=markdown_url,
        storage_key=md_storage_key,
        storage_version=STORAGE_VERSION,
        derived_from_id=content_hash,
        derived_kind="excel_to_markdown",
        name=markdown_display_name,
        size=markdown_size,
        mime="text/markdown",
    )
    return ExcelBlock(
        id=content_hash,
        type="excel",
        url=excel_url,
        storage_key=excel_storage_key,
        storage_version=STORAGE_VERSION,
        name=excel_display_name,
        size=excel_size,
        mime=EXCEL_CONTENT_TYPE,
        markdown=markdown_block,
    )


async def _index_excel_markdown_or_raise(
    *,
    user_id: str,
    content_id: str,
    md_path: Path,
    file_name: str,
    original_size_bytes: int,
    processed_size_bytes: int,
) -> None:
    try:
        markdown_text = await asyncio.to_thread(md_path.read_text, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Chat excel markdown read failed before embedding",
            user_id=user_id,
            content_id=content_id,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(status_code=502, detail="读取 Markdown 文件失败") from exc

    try:
        await index_uploaded_text_chunks(
            user_id=user_id,
            content_id=content_id,
            text=markdown_text,
            file_name=file_name,
            source_kind="excel",
            text_format="markdown",
            original_size_bytes=original_size_bytes,
            processed_size_bytes=processed_size_bytes,
        )
    except KbFileChunkIndexingError as exc:
        logger.error(
            "Chat excel embedding indexing failed",
            user_id=user_id,
            content_id=content_id,
            md_path=str(md_path),
            error=exc,
        )
        raise HTTPException(
            status_code=502, detail=f"Excel 分块向量入库失败：{exc}"
        ) from exc


async def save_chat_excel(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> ExcelBlock:
    """保存上传 Excel (.xlsx) 至会话 uploads 目录，并生成 derived Markdown。"""
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    if content_type != EXCEL_CONTENT_TYPE and not raw_filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="Excel 大小不能超过 10MB")
    if not chunk.startswith(_XLSX_MAGIC):
        raise HTTPException(status_code=400, detail="Excel 文件无效或已损坏")

    content_hash = _excel_sha256_hex(chunk)
    excel_display_name = sanitize_upload_display_name(
        file.filename,
        ext=".xlsx",
        default_stem="spreadsheet",
    )
    excel_display_name = allocate_unique_display_name(
        user_id, conversation_id, excel_display_name
    )
    excel_storage_key = build_conversation_storage_key(
        conversation_id, excel_display_name
    )
    md_storage_key = build_derived_markdown_storage_key(
        conversation_id, excel_display_name
    )

    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    dest: Path = upload_dir / excel_display_name
    md_path = upload_dir / "derived" / f"{Path(excel_display_name).stem}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(dest.write_bytes, chunk)

    converter = ExcelMarkdownConverter()
    try:
        markdown = await asyncio.to_thread(converter.convert_excel_to_markdown, dest)
        await asyncio.to_thread(converter.save_markdown, markdown, md_path)
    except ExcelMarkdownConversionError as exc:
        logger.error(
            "Chat excel markdown conversion failed",
            user_id=user_id,
            storage_key=excel_storage_key,
            error=exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Excel 转 Markdown 失败：{exc}",
        ) from exc

    markdown_size = md_path.stat().st_size
    excel_size = dest.stat().st_size
    await _index_excel_markdown_or_raise(
        user_id=user_id,
        content_id=content_hash,
        md_path=md_path,
        file_name=excel_display_name,
        original_size_bytes=excel_size,
        processed_size_bytes=markdown_size,
    )

    logger.info(
        "Chat excel saved",
        user_id=user_id,
        conversation_id=conversation_id,
        storage_key=excel_storage_key,
        bytes=excel_size,
        markdown_storage_key=md_storage_key,
        markdown_bytes=markdown_size,
    )
    return _build_excel_block(
        content_hash=content_hash,
        user_id=user_id,
        excel_display_name=excel_display_name,
        excel_storage_key=excel_storage_key,
        md_storage_key=md_storage_key,
        excel_size=excel_size,
        markdown_size=markdown_size,
    )
