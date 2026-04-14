"""聊天附件上传：落盘到 data/user_data/{user_id}/uploads/"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, ImageSequence

from app.schemas.chat import ImageBlock, PdfBlock
from app.utils.common import gen_uuid
from app.utils.logger import logger

_BACKEND_ROOT = Path(__file__).resolve().parents[3]

MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_CHAT_IMAGE_EDGE = 1024  # 最长边像素上限（等比例缩放）
CHAT_ATTACHMENT_PREVIEW_PREFIX = "/api/file/preview"

_ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
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


def _user_upload_dir(user_id: str) -> Path:
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


def _encode_single_frame(im: Image.Image, ext: str) -> bytes:
    buf = BytesIO()
    ext_lower = ext.lower()
    if ext_lower in (".jpg", ".jpeg"):
        im.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    elif ext_lower == ".png":
        im.save(buf, format="PNG", optimize=True)
    elif ext_lower == ".gif":
        im.save(buf, format="GIF")
    elif ext_lower == ".webp":
        im.save(buf, format="WEBP", quality=85, method=6)
    else:
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    return buf.getvalue()


def _encode_animated(
    frames: list[Image.Image],
    durations: list[int],
    loop: int,
    ext: str,
) -> bytes:
    buf = BytesIO()
    ext_lower = ext.lower()
    if ext_lower == ".gif":
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
        )
    elif ext_lower == ".webp":
        frames[0].save(
            buf,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            quality=85,
            method=6,
        )
    elif ext_lower == ".png":
        frames[0].save(
            buf,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
        )
    else:
        raise HTTPException(status_code=400, detail="无效的图片文件")
    return buf.getvalue()


def _downscale_image_bytes(data: bytes, ext: str) -> bytes:
    """最长边不超过 MAX_CHAT_IMAGE_EDGE，等比例缩小；已足够小则原样返回。"""
    try:
        im: Image.Image = cast(Image.Image, Image.open(BytesIO(data)))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="图片文件无效或已损坏",
        ) from None

    try:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        if max(w, h) <= MAX_CHAT_IMAGE_EDGE:
            return data

        n_frames = getattr(im, "n_frames", 1)
        loop = im.info.get("loop", 0)
        default_duration = im.info.get("duration", 100)

        if n_frames <= 1:
            im_copy = im.copy()
            im_copy.thumbnail(
                (MAX_CHAT_IMAGE_EDGE, MAX_CHAT_IMAGE_EDGE),
                Image.Resampling.LANCZOS,
            )
            return _encode_single_frame(im_copy, ext)

        durations: list[int] = []
        frames: list[Image.Image] = []
        for frame in ImageSequence.Iterator(im):
            frame = frame.copy()
            frame.thumbnail(
                (MAX_CHAT_IMAGE_EDGE, MAX_CHAT_IMAGE_EDGE),
                Image.Resampling.LANCZOS,
            )
            durations.append(frame.info.get("duration", default_duration))
            frames.append(frame)
        return _encode_animated(frames, durations, loop, ext)
    finally:
        im.close()


async def save_chat_image(*, user_id: str, file: UploadFile) -> ImageBlock:
    """保存上传图片并返回 ImageBlock（url 为站内预览路径）。"""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="仅支持 JPEG、PNG、GIF、WebP 图片",
        )
    ext = _ALLOWED_CONTENT_TYPES[content_type]
    block_id = gen_uuid()
    filename = f"{block_id}{ext}"

    upload_dir = _user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")
    processed = _downscale_image_bytes(chunk, ext)
    dest.write_bytes(processed)
    stored_size = len(processed)
    display_name = sanitize_upload_display_name(
        file.filename,
        ext=ext,
        default_stem="image",
    )

    logger.info(
        "Chat image saved",
        user_id=user_id,
        filename=filename,
        bytes=stored_size,
    )

    url = build_attachment_preview_url(user_id, filename)
    mime_normalized = (
        "image/jpeg" if content_type in ("image/jpeg", "image/jpg") else content_type
    )
    return ImageBlock(
        id=block_id,
        type="image",
        url=url,
        name=display_name,
        size=stored_size,
        mime=mime_normalized,
    )


async def save_chat_pdf(*, user_id: str, file: UploadFile) -> PdfBlock:
    """保存上传 PDF 并返回 PdfBlock（url 为站内预览路径）。"""
    content_type = (file.content_type or "").lower()
    if content_type != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    block_id = gen_uuid()
    filename = f"{block_id}.pdf"

    upload_dir = _user_upload_dir(user_id)
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


async def save_chat_attachment(
    *, user_id: str, file: UploadFile
) -> ImageBlock | PdfBlock:
    content_type = (file.content_type or "").lower()
    if content_type == PDF_CONTENT_TYPE:
        return await save_chat_pdf(user_id=user_id, file=file)
    return await save_chat_image(user_id=user_id, file=file)


def media_type_for_preview(filename: str) -> str:
    lower = filename.lower()
    for suf, mt in _EXT_TO_MEDIA_TYPE.items():
        if lower.endswith(suf):
            return mt
    return "application/octet-stream"
