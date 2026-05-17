"""聊天附件通用能力：路径、展示名、预览 URL、上传分发。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from app.models import AttachmentFileDb, ConversationAttachmentDb, ConversationDb
from app.schemas.chat import AttachmentBlock

_BACKEND_ROOT = Path(__file__).resolve().parents[3]

MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB
CHAT_ATTACHMENT_PREVIEW_PREFIX = "/api/file/preview"
PDF_CONTENT_TYPE: Literal["application/pdf"] = "application/pdf"
MARKDOWN_CONTENT_TYPE: Literal["text/markdown"] = "text/markdown"

# 单段 basename：首字符为字母/数字，其余可含 ._-；白名单后缀，不固定 UUID/哈希分段与位数。
_FILENAME_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,237}\.(jpg|jpeg|png|gif|webp|pdf|md)$",
    re.IGNORECASE,
)
_STORAGE_KEY_RE = re.compile(
    r"^(raw|derived)/[A-Fa-f0-9][A-Fa-f0-9._-]{0,237}\.(jpg|jpeg|png|gif|webp|pdf|md)$",
    re.IGNORECASE,
)
_PREVIEW_PREFIX = f"{CHAT_ATTACHMENT_PREVIEW_PREFIX}/"
STORAGE_VERSION = 2

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": PDF_CONTENT_TYPE,
    ".md": "text/markdown",
}

_STEM_SAFE_RE = re.compile(r"[^\w\-. \u0080-\uFFFF]+", re.UNICODE)


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


def get_user_upload_dir(user_id: str) -> Path:
    if not user_id or "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=400, detail="无效的用户 ID")
    return _BACKEND_ROOT / "data" / "user_data" / user_id / "uploads"


def get_user_shared_upload_dir(user_id: str) -> Path:
    if not user_id or "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=400, detail="无效的用户 ID")
    return _BACKEND_ROOT / "data" / "user_data" / user_id / "uploads"


def build_raw_storage_key(content_id: str, ext: str) -> str:
    ext_norm = ext if ext.startswith(".") else f".{ext}"
    return f"raw/{content_id}{ext_norm.lower()}"


def build_derived_markdown_storage_key(content_id: str) -> str:
    return f"derived/{content_id}.md"


def user_upload_file_path(user_id: str, storage_key_or_filename: str) -> Path:
    """校验 storage_key/旧文件名并返回磁盘路径；非法参数与越界均 404。"""
    if not user_id or "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    if "/" in storage_key_or_filename:
        return shared_upload_file_path(user_id, storage_key_or_filename)
    if not _FILENAME_RE.match(storage_key_or_filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    base = (_BACKEND_ROOT / "data" / "user_data" / user_id / "uploads").resolve()
    target = (base / storage_key_or_filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


def shared_upload_file_path(user_id: str, storage_key: str) -> Path:
    """校验 storage_key 并返回 shared/uploads 下的磁盘路径。"""
    if not _STORAGE_KEY_RE.match(storage_key):
        raise HTTPException(status_code=404, detail="文件不存在")
    base = get_user_shared_upload_dir(user_id).resolve()
    target = (base / storage_key).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


def resolve_markdown_path_for_content_id(user_id: str, content_id: str) -> Path | None:
    """按新旧存储位置查找附件 Markdown 全文。"""
    candidates = (
        get_user_shared_upload_dir(user_id)
        / build_derived_markdown_storage_key(content_id),
        get_user_shared_upload_dir(user_id) / build_raw_storage_key(content_id, ".md"),
        get_user_upload_dir(user_id) / f"{content_id}.md",
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def _storage_key_from_preview_url(ref: str, user_id: str) -> str | None:
    path = urlparse(ref).path
    prefix = f"{_PREVIEW_PREFIX}{user_id}/"
    if not path.startswith(prefix):
        return None
    value = unquote(path[len(prefix) :])
    return value or None


def resolve_file_ref(
    *,
    ref: str,
    user_id: str,
    conversation_id: str | None = None,
    db: Session | None = None,
) -> Path:
    """解析旧 URL、新 storage_key URL、storage_key 或内容 id 到真实文件路径。"""
    storage_key = _storage_key_from_preview_url(ref, user_id)
    if storage_key is None and "/" in ref:
        storage_key = ref

    if storage_key is not None:
        if "/" in storage_key and conversation_id and db is not None:
            mounted = db.exec(
                select(ConversationAttachmentDb).where(
                    ConversationAttachmentDb.conversation_id == conversation_id,
                    ConversationAttachmentDb.user_id == user_id,
                    ConversationAttachmentDb.storage_key == storage_key,
                )
            ).first()
            if mounted is None:
                raise HTTPException(status_code=404, detail="文件不存在")
        path = user_upload_file_path(user_id, storage_key)
        if path.is_file():
            return path

    if db is not None and conversation_id:
        mounts = db.exec(
            select(ConversationAttachmentDb).where(
                ConversationAttachmentDb.conversation_id == conversation_id,
                ConversationAttachmentDb.user_id == user_id,
            )
        ).all()
        for mount in mounts:
            attachment_file = db.get(AttachmentFileDb, mount.attachment_file_id)
            if attachment_file is None or attachment_file.content_id != ref:
                continue
            path = user_upload_file_path(user_id, attachment_file.storage_key)
            if path.is_file():
                return path
            if attachment_file.legacy_source:
                legacy_path = Path(attachment_file.legacy_source)
                if legacy_path.is_file():
                    return legacy_path

    legacy_key = _storage_key_from_preview_url(ref, user_id) or ref
    return user_upload_file_path(user_id, legacy_key)


def upsert_attachment_file(
    *,
    db: Session | None,
    user_id: str,
    content_id: str,
    storage_key: str,
    kind: str,
    mime: str,
    size: int,
    display_name: str,
    derived_from_id: str | None = None,
    derived_kind: str | None = None,
    legacy_source: str | None = None,
) -> AttachmentFileDb | None:
    if db is None:
        return None
    existing = db.exec(
        select(AttachmentFileDb).where(
            AttachmentFileDb.user_id == user_id,
            AttachmentFileDb.storage_key == storage_key,
        )
    ).first()
    if existing is not None:
        existing.content_id = content_id
        existing.kind = kind
        existing.mime = mime
        existing.size = size
        existing.display_name = display_name
        existing.derived_from_id = derived_from_id
        existing.derived_kind = derived_kind
        existing.legacy_source = legacy_source
        existing.storage_version = STORAGE_VERSION
        db.add(existing)
        db.flush()
        return existing

    attachment_file = AttachmentFileDb(
        user_id=user_id,
        content_id=content_id,
        storage_key=storage_key,
        kind=kind,
        mime=mime,
        size=size,
        display_name=display_name,
        derived_from_id=derived_from_id,
        derived_kind=derived_kind,
        legacy_source=legacy_source,
        storage_version=STORAGE_VERSION,
    )
    db.add(attachment_file)
    db.flush()
    return attachment_file


def mount_conversation_attachment(
    *,
    db: Session | None,
    user_id: str,
    conversation_id: str | None,
    attachment_file: AttachmentFileDb | None,
) -> None:
    if db is None or conversation_id is None or attachment_file is None:
        return
    conversation = db.get(ConversationDb, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="对话不存在")

    existing = db.exec(
        select(ConversationAttachmentDb).where(
            ConversationAttachmentDb.conversation_id == conversation_id,
            ConversationAttachmentDb.storage_key == attachment_file.storage_key,
        )
    ).first()
    if existing is not None:
        return
    db.add(
        ConversationAttachmentDb(
            conversation_id=conversation_id,
            user_id=user_id,
            attachment_file_id=attachment_file.id,
            storage_key=attachment_file.storage_key,
        )
    )
    db.flush()


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
    conversation_id: str | None = None,
    db: Session | None = None,
) -> AttachmentBlock:
    from app.services.chat_upload.image import save_chat_image
    from app.services.chat_upload.markdown import save_chat_markdown
    from app.services.chat_upload.pdf import save_chat_pdf

    content_type = (file.content_type or "").lower()
    raw_filename = (file.filename or "").lower()
    if content_type == PDF_CONTENT_TYPE:
        return await save_chat_pdf(
            user_id=user_id, file=file, conversation_id=conversation_id, db=db
        )
    if raw_filename.endswith(".md") or raw_filename.endswith(".markdown"):
        return await save_chat_markdown(
            user_id=user_id, file=file, conversation_id=conversation_id, db=db
        )
    return await save_chat_image(
        user_id=user_id, file=file, conversation_id=conversation_id, db=db
    )
