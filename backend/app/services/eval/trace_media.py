"""解析 trace IO 中的图片引用，还原为 data URI 供裁判模型（多模态）使用。

Langfuse 上报开启 media 上传后（``LANGFUSE__REPORT_IMAGES=true`` + S3 media endpoint），
SDK 会把消息里的 base64 data URI 替换为媒体引用标记，形如：

    @@@langfuseMedia:type=image/jpeg|id=<media_id>|source=base64_data_uri@@@

图片本体存 MinIO。取回路径：
1. ``GET /api/public/media/{media_id}``（basic auth: public/secret key）→ 元数据 + 签名 URL；
2. ``GET {url}`` → 图片字节 → 拼回 ``data:<mime>;base64,...``。
"""

from __future__ import annotations

import base64
import re

import httpx

from app.core.config import settings
from app.utils.logger import logger

LANGFUSE_MEDIA_RE = re.compile(r"^@@@langfuseMedia:(?P<fields>[^@]+)@@@$")
MEDIA_FETCH_TIMEOUT_S = 30.0
MAX_IMAGE_BYTES = 20 * 1024 * 1024
_CACHE_MAX_ENTRIES = 64

# media_id → data URI（批量评估同图多 trace 时避免重复下载）
_data_uri_cache: dict[str, str] = {}


def _parse_media_marker(ref: str) -> tuple[str, str] | None:
    """解析 langfuseMedia 标记，返回 (media_id, content_type)。"""
    match = LANGFUSE_MEDIA_RE.match(ref.strip())
    if match is None:
        return None
    media_id = ""
    content_type = ""
    for part in match.group("fields").split("|"):
        key, _, value = part.partition("=")
        if key == "id":
            media_id = value.strip()
        elif key == "type":
            content_type = value.strip()
    if not media_id:
        return None
    return media_id, content_type


def _cache_put(media_id: str, data_uri: str) -> None:
    if len(_data_uri_cache) >= _CACHE_MAX_ENTRIES:
        _data_uri_cache.clear()
    _data_uri_cache[media_id] = data_uri


def _fetch_langfuse_media(media_id: str, content_type: str) -> str | None:
    """通过 Langfuse Media API 取回图片字节，返回 data URI。"""
    cached = _data_uri_cache.get(media_id)
    if cached:
        return cached

    cfg = settings.langfuse
    if not cfg.host or not cfg.public_key or not cfg.secret_key:
        logger.warning("Cannot fetch langfuse media: langfuse config missing", media_id=media_id)
        return None

    try:
        with httpx.Client(
            timeout=MEDIA_FETCH_TIMEOUT_S,
            auth=(cfg.public_key, cfg.secret_key),
        ) as http:
            meta_resp = http.get(
                f"{cfg.host.rstrip('/')}/api/public/media/{media_id}",
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            content_length = int(meta.get("contentLength") or 0)
            if content_length > MAX_IMAGE_BYTES:
                logger.warning(
                    "Skip langfuse media: too large",
                    media_id=media_id,
                    content_length=content_length,
                )
                return None

            content_url = str(meta.get("url") or "")
            if not content_url:
                logger.warning("Skip langfuse media: no content url", media_id=media_id)
                return None

            content_resp = http.get(content_url)
            content_resp.raise_for_status()
            raw = content_resp.content
    except Exception as exc:
        logger.warning(
            "Failed to fetch langfuse media",
            media_id=media_id,
            error=exc,
            error_type=type(exc).__name__,
        )
        return None

    if len(raw) > MAX_IMAGE_BYTES:
        logger.warning(
            "Skip langfuse media: too large",
            media_id=media_id,
            content_length=len(raw),
        )
        return None

    mime = str(meta.get("contentType") or content_type or "image/jpeg")
    data_uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    _cache_put(media_id, data_uri)
    return data_uri


def resolve_image_ref(ref: str) -> str | None:
    """把单个图片引用解析为裁判模型可用的 URL / data URI。

    - ``data:image/...``：原样放行
    - langfuseMedia 标记：取回字节拼 data URI
    - ``http(s)://``：原样放行（由裁判模型侧决定是否拉取）
    - 其它 / 取回失败：返回 None（跳过该图，不影响评分流程）
    """
    ref = ref.strip()
    if not ref:
        return None
    lower = ref.lower()
    if lower.startswith("data:image/") and ";base64," in lower:
        return ref
    marker = _parse_media_marker(ref)
    if marker is not None:
        media_id, content_type = marker
        return _fetch_langfuse_media(media_id, content_type)
    if lower.startswith("http://") or lower.startswith("https://"):
        return ref
    return None


def resolve_image_refs(refs: list[str]) -> list[str]:
    """批量解析图片引用，丢弃失败项。"""
    resolved: list[str] = []
    for ref in refs:
        data_uri = resolve_image_ref(ref)
        if data_uri:
            resolved.append(data_uri)
    return resolved
