"""聊天附件通用能力：路径、展示名、预览 URL、上传分发。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, UploadFile

from app.schemas.chat import ImageBlock, PdfBlock

_BACKEND_ROOT = Path(__file__).resolve().parents[3]

MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB
CHAT_ATTACHMENT_PREVIEW_PREFIX = "/api/file/preview"
PDF_CONTENT_TYPE: Literal["application/pdf"] = "application/pdf"

_FILENAME_RE = re.compile(
    (
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{12}\.(jpg|jpeg|png|gif|webp|pdf)$"
    ),
    re.IGNORECASE,
)

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": PDF_CONTENT_TYPE,
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


def build_attachment_preview_url(user_id: str, filename: str) -> str:
    return f"{CHAT_ATTACHMENT_PREVIEW_PREFIX}/{user_id}/{filename}"


def get_user_upload_dir(user_id: str) -> Path:
    if not user_id or "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=400, detail="无效的用户 ID")
    return _BACKEND_ROOT / "data" / "user_data" / user_id / "uploads"


def user_upload_file_path(user_id: str, filename: str) -> Path:
    """校验文件名并返回磁盘路径；非法参数与越界均 404（公开预览）。"""
    if not user_id or "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    base = (_BACKEND_ROOT / "data" / "user_data" / user_id / "uploads").resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


def media_type_for_preview(filename: str) -> str:
    lower = filename.lower()
    for suf, mt in _EXT_TO_MEDIA_TYPE.items():
        if lower.endswith(suf):
            return mt
    return "application/octet-stream"


async def save_chat_attachment(
    *, user_id: str, file: UploadFile
) -> ImageBlock | PdfBlock:
    from app.services.base_service.chat_image_service import save_chat_image
    from app.services.base_service.chat_pdf_service import save_chat_pdf

    content_type = (file.content_type or "").lower()
    if content_type == PDF_CONTENT_TYPE:
        return await save_chat_pdf(user_id=user_id, file=file)
    return await save_chat_image(user_id=user_id, file=file)
