"""多模态 content 序列化/反序列化与文本提取"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.content import (
    ContentPart,
    FileContentPart,
    FileObject,
    ImageContentPart,
    TextContentPart,
)

MAX_MARKDOWN_CHARS = 20_000
MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4MB：过大时降级为 artifact_url


def _looks_like_json_array(value: str) -> bool:
    s = (value or "").lstrip()
    return s.startswith("[") and s.endswith("]")


def parse_content_parts(content: str) -> list[ContentPart] | None:
    """若 content 是 ContentPart 数组的 JSON 字符串则解析，否则返回 None。"""
    if not content or not _looks_like_json_array(content):
        return None
    try:
        raw = json.loads(content)
    except Exception:
        return None
    if not isinstance(raw, list):
        return None

    parts: list[ContentPart] = []
    for item in raw:
        if not isinstance(item, dict) or "type" not in item:
            return None
        try:
            t = item.get("type")
            if t == "text":
                parts.append(TextContentPart.model_validate(item))
            elif t == "image":
                parts.append(ImageContentPart.model_validate(item))
            elif t == "file":
                parts.append(FileContentPart.model_validate(item))
            else:
                return None
        except ValidationError:
            return None
    return parts


def serialize_message_content(content: str | list[ContentPart]) -> str:
    """将用户消息 content 统一序列化为 DB 存储字符串。"""
    if isinstance(content, str):
        return content
    parts_jsonable: list[dict[str, Any]] = [p.model_dump(mode="json") for p in content]
    return json.dumps(parts_jsonable, ensure_ascii=False)


def extract_text_from_content(content: str | list[ContentPart] | None) -> str:
    """只提取 text 类型，用于检索/日志/工具调用/最终回复。"""
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    chunks: list[str] = []
    for p in content:
        if isinstance(p, TextContentPart):
            chunks.append(p.text)
    return "\n".join([c for c in chunks if c.strip()]).strip()


def _validate_stored_filename(name: str) -> bool:
    return bool(name) and ("/" not in name) and ("\\" not in name)


def _uploads_dir(conversation_id: str) -> Path:
    return Path("./data/conversations") / conversation_id / "user-data" / "uploads"


def _file_local_path(file_obj: FileObject, filename: str) -> Path | None:
    if not _validate_stored_filename(filename):
        return None
    return _uploads_dir(file_obj.conversation_id) / filename


def _try_read_markdown_text(file_obj: FileObject) -> str | None:
    if not file_obj.markdown_file:
        return None
    path = _file_local_path(file_obj, file_obj.markdown_file)
    if not path or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > MAX_MARKDOWN_CHARS:
        text = text[:MAX_MARKDOWN_CHARS] + "\n\n[内容过长已截断]"
    return text


def _try_image_data_url(file_obj: FileObject) -> str | None:
    path = _file_local_path(file_obj, file_obj.stored_filename)
    if not path or not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    mime = file_obj.mime_type or mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def extract_image_blocks_from_content(
    content: str | list[ContentPart] | None,
) -> list[dict[str, Any]]:
    """从多模态内容中提取图片 blocks（优先 base64 data URL，失败则降级为 artifact_url）。"""
    if content is None:
        return []
    parts: list[ContentPart] | None
    if isinstance(content, str):
        parts = parse_content_parts(content)
        if parts is None:
            return []
    else:
        parts = content

    blocks: list[dict[str, Any]] = []
    for p in parts:
        if not isinstance(p, ImageContentPart):
            continue
        url = _try_image_data_url(p.image) or p.image.artifact_url
        blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks


def content_parts_to_openai_content(
    parts: list[ContentPart] | str,
) -> str | list[dict[str, Any]]:
    """将 ContentPart 转为 OpenAI-compatible 的多模态 content 列表。

    - 图片：优先注入 base64 data URL；失败则降级为 artifact_url
    - 文件：若存在 markdown_file，自动注入 markdown 文本块；否则注入链接文本
    """
    if isinstance(parts, str):
        return parts

    out: list[dict[str, Any]] = []
    for p in parts:
        if isinstance(p, TextContentPart):
            out.append({"type": "text", "text": p.text})
        elif isinstance(p, ImageContentPart):
            url = _try_image_data_url(p.image) or p.image.artifact_url
            out.append(
                {
                    "type": "image_url",
                    "image_url": {"url": url},
                }
            )
        elif isinstance(p, FileContentPart):
            f = p.file
            md_text = _try_read_markdown_text(f)
            if md_text:
                out.append(
                    {"type": "text", "text": f"[文件] {f.filename}\n\n{md_text}"}
                )
            else:
                url = f.markdown_artifact_url or f.artifact_url
                out.append({"type": "text", "text": f"[文件] {f.filename} {url}"})
    return out
