"""聊天附件通用能力：路径、展示名、预览 URL、上传分发。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from app.models import ConversationDb
from app.schemas.chat import AttachmentBlock
from app.vfs.paths import get_paths

MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB
CHAT_ATTACHMENT_PREVIEW_PREFIX = "/api/file/preview"
PDF_CONTENT_TYPE: Literal["application/pdf"] = "application/pdf"
MARKDOWN_CONTENT_TYPE: Literal["text/markdown"] = "text/markdown"
EXCEL_CONTENT_TYPE: Literal[
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_UUID_SEGMENT = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_STORAGE_KEY_CONV_TOP_RE = re.compile(
    rf"^{_UUID_SEGMENT}/[^/\\]+\.(jpg|jpeg|png|gif|webp|pdf|md|xlsx)$",
    re.IGNORECASE,
)
_STORAGE_KEY_CONV_DERIVED_RE = re.compile(
    rf"^{_UUID_SEGMENT}/derived/[^/\\]+\.md$",
    re.IGNORECASE,
)
STORAGE_VERSION = 4

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": PDF_CONTENT_TYPE,
    ".md": "text/markdown",
    ".xlsx": EXCEL_CONTENT_TYPE,
}

_STEM_SAFE_RE = re.compile(r"[^\w\-. \u0080-\uFFFF]+", re.UNICODE)


def _validate_id(value: str, *, label: str = "ID") -> str:
    normalized = (value or "").strip()
    if (
        not normalized
        or "/" in normalized
        or "\\" in normalized
        or ".." in normalized
        or normalized.startswith(".")
    ):
        raise HTTPException(status_code=400, detail=f"无效的{label}")
    return normalized


def sanitize_upload_display_name(
    raw: str | None, *, ext: str, default_stem: str
) -> str:
    """用户上传文件的展示名：去路径/控制字符/保留 Windows 非法字符，限制长度。"""
    ext_norm = ext if ext.startswith(".") else f".{ext}"
    stem = default_stem
    if raw:
        base = Path(str(raw)).name
        base = base.replace("\x00", "")
        base = "".join(c for c in base if ord(c) >= 32)
        base = re.sub(r'[<>:"|?*\\/]', "_", base)
        base = base.strip(" .")
        if base:
            stem_candidate = Path(base).stem
            stem_candidate = _STEM_SAFE_RE.sub("_", stem_candidate)
            stem_candidate = stem_candidate.strip(" ._-")
            if stem_candidate:
                stem = stem_candidate[:180]
    return f"{stem}{ext_norm}"


def build_attachment_preview_url(user_id: str, storage_key: str) -> str:
    return f"{CHAT_ATTACHMENT_PREVIEW_PREFIX}/{user_id}/{storage_key}"


def get_conversation_upload_dir(user_id: str, conversation_id: str) -> Path:
    safe_user_id = _validate_id(user_id, label="用户 ID")
    safe_conversation_id = _validate_id(conversation_id, label="会话 ID")
    path = get_paths().sandbox_uploads_dir(safe_user_id, safe_conversation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_conversation_storage_key(conversation_id: str, display_name: str) -> str:
    safe_conversation_id = _validate_id(conversation_id, label="会话 ID")
    if not display_name or "/" in display_name or "\\" in display_name:
        raise HTTPException(status_code=400, detail="无效的文件名")
    return f"{safe_conversation_id}/{display_name}"


def build_derived_markdown_storage_key(
    conversation_id: str, pdf_display_name: str
) -> str:
    stem = Path(pdf_display_name).stem
    if not stem or "/" in stem or "\\" in stem:
        raise HTTPException(status_code=400, detail="无效的文件名")
    safe_conversation_id = _validate_id(conversation_id, label="会话 ID")
    return f"{safe_conversation_id}/derived/{stem}.md"


def allocate_unique_display_name(
    user_id: str,
    conversation_id: str,
    display_name: str,
) -> str:
    upload_dir = get_conversation_upload_dir(user_id, conversation_id)
    candidate = display_name
    if not (upload_dir / candidate).exists():
        return candidate
    stem = Path(display_name).stem
    ext = Path(display_name).suffix
    counter = 1
    while True:
        candidate = f"{stem}({counter}){ext}"
        if not (upload_dir / candidate).exists():
            return candidate
        counter += 1


def _is_conversation_storage_key(storage_key: str) -> bool:
    return bool(
        _STORAGE_KEY_CONV_TOP_RE.match(storage_key)
        or _STORAGE_KEY_CONV_DERIVED_RE.match(storage_key)
    )


def _resolve_conversation_upload_path(user_id: str, storage_key: str) -> Path | None:
    """Resolve storage_key ``{conversation_id}/...`` on v4 layout."""
    if not _is_conversation_storage_key(storage_key):
        return None
    parts = storage_key.split("/", 1)
    if len(parts) != 2:
        return None
    conversation_id, relative = parts[0], parts[1]
    safe_user_id = _validate_id(user_id, label="用户 ID")
    safe_conversation_id = _validate_id(conversation_id, label="会话 ID")
    candidate = (
        get_paths().sandbox_uploads_dir(safe_user_id, safe_conversation_id) / relative
    )
    resolved = candidate.resolve()
    if resolved.is_file():
        return resolved
    return None


def shared_upload_file_path(user_id: str, storage_key: str) -> Path:
    """校验 storage_key 并返回磁盘路径。"""
    path = _resolve_conversation_upload_path(user_id, storage_key)
    if path is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return path


def try_resolve_upload_file_path(user_id: str, storage_key: str) -> Path | None:
    """Return upload path if the file exists, else None (no HTTPException)."""
    return _resolve_conversation_upload_path(user_id, storage_key)


def ensure_conversation_owned(
    db: Session | None,
    *,
    user_id: str,
    conversation_id: str,
) -> None:
    if db is None:
        return
    conversation = db.get(ConversationDb, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="对话不存在")


def media_type_for_preview(filename: str) -> str:
    lower = filename.lower()
    for suf, mt in _EXT_TO_MEDIA_TYPE.items():
        if lower.endswith(suf):
            return mt
    return "application/octet-stream"


async def save_chat_attachment(
    *,
    user_id: str,
    file: UploadFile,
    conversation_id: str,
    db: Session | None = None,
) -> AttachmentBlock:
    from app.services.chat_upload.excel import save_chat_excel
    from app.services.chat_upload.image import save_chat_image
    from app.services.chat_upload.markdown import save_chat_markdown
    from app.services.chat_upload.pdf import save_chat_pdf

    if not (conversation_id or "").strip():
        raise HTTPException(status_code=400, detail="conversation_id 为必填项")
    ensure_conversation_owned(db, user_id=user_id, conversation_id=conversation_id)

    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    if content_type == PDF_CONTENT_TYPE:
        return await save_chat_pdf(
            user_id=user_id,
            file=file,
            conversation_id=conversation_id,
            db=db,
        )
    if content_type == EXCEL_CONTENT_TYPE or raw_filename.endswith(".xlsx"):
        return await save_chat_excel(
            user_id=user_id,
            file=file,
            conversation_id=conversation_id,
            db=db,
        )
    if raw_filename.endswith(".md") or raw_filename.endswith(".markdown"):
        return await save_chat_markdown(
            user_id=user_id,
            file=file,
            conversation_id=conversation_id,
            db=db,
        )
    return await save_chat_image(
        user_id=user_id,
        file=file,
        conversation_id=conversation_id,
        db=db,
    )
