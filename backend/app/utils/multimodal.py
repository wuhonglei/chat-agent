"""Helpers for building multimodal OpenAI-compatible user messages."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.schemas.chat import (
    AttachmentFileInfo,
    AttachmentUploadInfo,
    ChatMessage,
    ContentBlock,
    ImageBlock,
    KbContextBlock,
    MarkdownBlock,
    PdfBlock,
    extract_user_text,
    normalize_content_blocks,
)
from app.services.chat_upload.attachment import try_resolve_upload_file_path
from app.utils.logger import logger
from app.vfs.config import vfs_config

_IMAGE_PREVIEW_PATH_PATTERNS = (re.compile(r"^/api/file/preview/([^/]+)/(.+)$"),)
_IMAGE_ONLY_PLACEHOLDER = "[用户发送了图片]"
_PDF_ONLY_PLACEHOLDER = "[用户发送了 PDF 文件]"
_MARKDOWN_ONLY_PLACEHOLDER = "[用户发送了 Markdown 文件]"


def has_image_block(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> bool:
    return any(
        isinstance(block, ImageBlock)
        for block in normalize_content_blocks(content_blocks)
    )


def has_pdf_block(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> bool:
    return any(
        isinstance(block, PdfBlock)
        for block in normalize_content_blocks(content_blocks)
    )


def has_markdown_block(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> bool:
    return any(
        isinstance(block, MarkdownBlock)
        for block in normalize_content_blocks(content_blocks)
    )


def extract_user_text_with_attachment_placeholder(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> str:
    normalized_blocks = normalize_content_blocks(content_blocks)
    text = extract_user_text(normalized_blocks)
    if text:
        return text
    if has_image_block(normalized_blocks):
        return _IMAGE_ONLY_PLACEHOLDER
    if has_pdf_block(normalized_blocks):
        return _PDF_ONLY_PLACEHOLDER
    if has_markdown_block(normalized_blocks):
        return _MARKDOWN_ONLY_PLACEHOLDER
    return ""


def collect_attachment_content_ids(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> set[str]:
    content_ids: set[str] = set()
    for block in normalize_content_blocks(content_blocks):
        if isinstance(block, MarkdownBlock):
            content_ids.add(block.id)
            continue
        if not isinstance(block, PdfBlock):
            continue
        content_ids.add(block.id)
        if block.markdown is not None and block.markdown.id:
            content_ids.add(block.markdown.id)
    return content_ids


def collect_attachment_content_ids_from_history_messages(
    history_messages: list[ChatMessage] | None,
) -> set[str]:
    content_ids: set[str] = set()
    for message in history_messages or []:
        if message.role != "user":
            continue
        content_ids.update(collect_attachment_content_ids(message.content_blocks))
    return content_ids


def resolve_storage_key_for_content_id(
    content_id: str,
    *,
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    history_messages: list[ChatMessage] | None,
) -> str | None:
    """在当前轮 blocks + 历史 user messages 中，按 id 查找 Markdown 的 storage_key。"""

    def _lookup(blocks: list[ContentBlock] | list[dict[str, Any]] | None) -> str | None:
        for block in normalize_content_blocks(blocks):
            if isinstance(block, MarkdownBlock) and block.id == content_id:
                return block.storage_key
            if (
                isinstance(block, PdfBlock)
                and block.markdown is not None
                and block.markdown.id == content_id
            ):
                return block.markdown.storage_key
        return None

    found = _lookup(content_blocks)
    if found is not None:
        return found

    for message in reversed(history_messages or []):
        if message.role != "user":
            continue
        found = _lookup(message.content_blocks)
        if found is not None:
            return found
    return None


def _storage_key_to_virtual_path(storage_key: str | None) -> str | None:
    """将会话上传 storage_key（{cid}/...）映射为 VFS uploads 虚拟路径。"""
    if not storage_key:
        return None
    parts = storage_key.split("/", 1)
    if len(parts) != 2 or not parts[1]:
        return None
    return f"{vfs_config.uploads_prefix}{parts[1]}"


def build_attachment_uploads(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    history_messages: list[ChatMessage] | None,
) -> list[AttachmentUploadInfo]:
    """构建 agent_mode 注入的上传文件清单。

    当前轮 blocks 标记 is_current_turn=True，历史 user 消息标记 False，
    按 storage_key 去重（当前轮优先）。
    """
    uploads: list[AttachmentUploadInfo] = []
    seen_storage_keys: set[str] = set()

    def _collect(
        blocks: list[ContentBlock] | list[dict[str, Any]] | None,
        *,
        is_current_turn: bool,
    ) -> None:
        for block in normalize_content_blocks(blocks):
            if not isinstance(block, (PdfBlock, MarkdownBlock, ImageBlock)):
                continue

            virtual_path = _storage_key_to_virtual_path(block.storage_key)
            if virtual_path is None or block.storage_key is None:
                continue
            if block.storage_key in seen_storage_keys:
                continue
            seen_storage_keys.add(block.storage_key)

            markdown: AttachmentFileInfo | None = None
            if isinstance(block, PdfBlock) and block.markdown is not None:
                md_virtual_path = _storage_key_to_virtual_path(
                    block.markdown.storage_key
                )
                if md_virtual_path is not None:
                    markdown = AttachmentFileInfo(
                        name=block.markdown.name,
                        type=block.markdown.type,
                        size=block.markdown.size,
                        virtual_path=md_virtual_path,
                    )

            uploads.append(
                AttachmentUploadInfo(
                    name=block.name,
                    type=block.type,
                    size=block.size,
                    virtual_path=virtual_path,
                    markdown=markdown,
                    is_current_turn=is_current_turn,
                )
            )

    _collect(content_blocks, is_current_turn=True)
    for message in reversed(history_messages or []):
        if message.role != "user":
            continue
        _collect(message.content_blocks, is_current_turn=False)

    return uploads


def build_title_user_message_for_llm(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    kb_context_blocks: list[KbContextBlock] | None = None,
) -> str | list[dict[str, Any]]:
    """Build title user message with wrapped text and optional images."""
    from app.prompts.prompt_utils import get_user_message_for_title

    normalized_blocks = normalize_content_blocks(content_blocks)
    query_text = extract_user_text_with_attachment_placeholder(normalized_blocks)
    wrapped = get_user_message_for_title(
        query_text, kb_context_blocks=kb_context_blocks
    )

    return build_user_content_for_llm(
        content_blocks,
        leading_text=wrapped,
        include_text_blocks=False,
    )


def build_user_content_for_llm(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    *,
    leading_text: str | None = None,
    include_text_blocks: bool = True,
) -> str | list[dict[str, Any]]:
    """Convert content blocks to OpenAI-compatible user content.

    - Text-only message -> string content
    - Message with images -> list content with text/image_url parts
    """
    normalized_blocks = normalize_content_blocks(content_blocks)
    has_image = has_image_block(normalized_blocks)

    text = _build_text_content(
        normalized_blocks,
        leading_text=leading_text,
        include_text_blocks=include_text_blocks,
    )
    if not has_image:
        return text

    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"type": "text", "text": text})

    for block in normalized_blocks:
        if not isinstance(block, ImageBlock):
            continue
        image_url = _build_image_data_url(block)
        if not image_url:
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )

    if not parts:
        return text
    return parts


def _build_text_content(
    content_blocks: list[ContentBlock],
    *,
    leading_text: str | None,
    include_text_blocks: bool,
) -> str:
    segments: list[str] = []
    for block in content_blocks:
        if isinstance(block, KbContextBlock) and block.content.strip():
            segments.append(block.content.strip())
    if leading_text and leading_text.strip():
        segments.append(leading_text.strip())
    if include_text_blocks:
        block_text = extract_user_text(content_blocks)
        if block_text:
            segments.append(block_text)
    return "\n".join(segments).strip()


def _build_image_data_url(block: ImageBlock) -> str | None:
    if block.url.startswith("data:image/"):
        return block.url

    path = _resolve_image_path(block.url)
    if path is None:
        logger.warning("Skip image block: invalid preview URL", image_url=block.url)
        return None
    if not path.is_file():
        logger.warning("Skip image block: image file not found", image_url=block.url)
        return None

    mime = block.mime if block.mime.startswith("image/") else "image/jpeg"
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception as exc:
        logger.warning(
            "Skip image block: failed reading image bytes",
            image_url=block.url,
            error=exc,
        )
        return None
    return f"data:{mime};base64,{encoded}"


def _resolve_image_path(url: str) -> Path | None:
    parsed = urlparse(url)
    raw_path = parsed.path
    match = None
    for pattern in _IMAGE_PREVIEW_PATH_PATTERNS:
        match = pattern.match(raw_path)
        if match:
            break
    if match is None:
        return None

    user_id = unquote(match.group(1))
    storage_key = unquote(match.group(2))
    return try_resolve_upload_file_path(user_id, storage_key)
