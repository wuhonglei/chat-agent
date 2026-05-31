"""用户头像路径与校验工具。"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings

AVATAR_URL_PREFIX = "/api/avatars/"

_AVATAR_FILENAME_RE = re.compile(
    r"^(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r"\.(?P<ext>jpg|jpeg|png|gif|webp)$",
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
    return _AVATAR_FILENAME_RE.fullmatch(filename) is not None


def _canonical_avatar_filename(filename: str) -> str:
    """从正则捕获组重建文件名，避免将用户输入直接拼入路径。"""
    match = _AVATAR_FILENAME_RE.fullmatch(filename)
    if match is None:
        raise InvalidAvatarError(f"无效的头像文件名: {filename}")
    return f"{match.group('uuid')}.{match.group('ext').lower()}"


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
    safe_name = _canonical_avatar_filename(filename)
    base_dir = Path(settings.storage.avatar_dir).resolve()
    # codeql[py/path-injection]: safe_name 仅由 UUID+扩展名正则捕获组重建，不含路径分隔符；
    # resolve 后须落在 avatar_dir 内（relative_to 校验），可防御路径遍历。
    candidate = (base_dir / safe_name).resolve()
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
