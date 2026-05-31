"""用户头像路径与校验工具。"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings

AVATAR_URL_PREFIX = "/api/avatars/"

_AVATAR_FILENAME_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"\.(jpg|jpeg|png|gif|webp)$",
    re.IGNORECASE,
)

_ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class InvalidAvatarError(ValueError):
    """头像字段格式不合法。"""


def is_valid_avatar_filename(filename: str) -> bool:
    return bool(_AVATAR_FILENAME_RE.match(filename))


def avatar_storage_path(filename: str) -> str:
    if not is_valid_avatar_filename(filename):
        raise InvalidAvatarError(f"无效的头像文件名: {filename}")
    return f"{AVATAR_URL_PREFIX}{filename}"


def avatar_filename_from_storage(value: str) -> str:
    """从 DB 存储路径解析磁盘文件名。"""
    if not value.startswith(AVATAR_URL_PREFIX):
        raise InvalidAvatarError(f"非本地头像路径: {value}")
    filename = value[len(AVATAR_URL_PREFIX) :]
    if not is_valid_avatar_filename(filename):
        raise InvalidAvatarError(f"无效的头像路径: {value}")
    return filename


def avatar_local_path(filename: str) -> Path:
    if not is_valid_avatar_filename(filename):
        raise InvalidAvatarError(f"无效的头像文件名: {filename}")

    base_dir = Path(settings.storage.avatar_dir).resolve()
    candidate = (base_dir / filename).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as e:
        raise InvalidAvatarError(f"无效的头像文件名: {filename}") from e

    return candidate


def is_cos_avatar_url(value: str) -> bool:
    if not value.startswith(("http://", "https://")):
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    return "myqcloud.com" in host and "/avatars/" in path


def filename_from_cos_url(url: str) -> str | None:
    """从 COS 头像 URL 解析文件名（路径最后一段）。"""
    if not is_cos_avatar_url(url):
        return None
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if is_valid_avatar_filename(name):
        return name
    return None


def normalize_avatar_for_storage(value: str) -> str:
    """
    写入 users.avatar 前校验。

    - http(s):// 外链（如微信）原样保留
    - /api/avatars/{合法filename} 原样保留
    - 其它格式拒绝
    """
    stripped = (value or "").strip()
    if not stripped:
        raise InvalidAvatarError("头像不能为空")

    if stripped.startswith(("http://", "https://")):
        if is_cos_avatar_url(stripped):
            raise InvalidAvatarError("不支持 COS 头像外链，请使用 /api/avatars/ 路径")
        return stripped

    if stripped.startswith(AVATAR_URL_PREFIX):
        filename = stripped[len(AVATAR_URL_PREFIX) :]
        if not is_valid_avatar_filename(filename):
            raise InvalidAvatarError(f"无效的头像路径: {stripped}")
        return stripped

    raise InvalidAvatarError("头像须为 /api/avatars/{filename} 或 http(s) 外链")


def media_type_for_avatar(filename: str) -> str:
    lower = filename.lower()
    for suf, mt in _EXT_TO_MEDIA_TYPE.items():
        if lower.endswith(suf):
            return mt
    return "application/octet-stream"


def assert_allowed_upload_extension(file_ext: str) -> None:
    ext = file_ext.lower() if file_ext else ""
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise InvalidAvatarError(f"不支持的头像格式: {file_ext or '(无扩展名)'}")
