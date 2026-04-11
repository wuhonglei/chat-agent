"""Helpers for building multimodal OpenAI-compatible user messages."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.schemas.chat import (
    ContentBlock,
    ImageBlock,
    extract_user_text,
    normalize_content_blocks,
)
from app.services.base_service.chat_image_service import user_upload_file_path
from app.utils.logger import logger

_IMAGE_PREVIEW_PATH_RE = re.compile(r"^/api/file/image/preview/([^/]+)/([^/]+)$")
_IMAGE_ONLY_PLACEHOLDER = "[用户发送了图片]"


def has_image_block(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> bool:
    return any(
        isinstance(block, ImageBlock)
        for block in normalize_content_blocks(content_blocks)
    )


def extract_user_text_with_image_placeholder(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    *,
    placeholder: str = _IMAGE_ONLY_PLACEHOLDER,
) -> str:
    normalized_blocks = normalize_content_blocks(content_blocks)
    text = extract_user_text(normalized_blocks)
    if text:
        return text
    if has_image_block(normalized_blocks):
        return placeholder
    return ""


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
    match = _IMAGE_PREVIEW_PATH_RE.match(raw_path)
    if not match:
        return None

    user_id = unquote(match.group(1))
    filename = unquote(match.group(2))
    try:
        return user_upload_file_path(user_id, filename)
    except Exception:
        return None
