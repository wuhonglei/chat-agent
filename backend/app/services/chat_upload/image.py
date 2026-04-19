"""聊天附件上传：图片处理服务。"""

from __future__ import annotations

from io import BytesIO
from typing import cast

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, ImageSequence

from app.schemas.chat import ImageBlock
from app.services.chat_upload.attachment import (
    MAX_CHAT_ATTACHMENT_BYTES,
    build_attachment_preview_url,
    get_user_upload_dir,
    sanitize_upload_display_name,
)
from app.utils.common import gen_uuid
from app.utils.logger import logger

MAX_CHAT_IMAGE_EDGE = 1024  # 最长边像素上限（等比例缩放）

_ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


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

    chunk = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    if len(chunk) > MAX_CHAT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    ext = _ALLOWED_CONTENT_TYPES[content_type]
    block_id = gen_uuid()
    filename = f"{block_id}{ext}"

    upload_dir = get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename

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
