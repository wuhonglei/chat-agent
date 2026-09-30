"""vision_analyze: load an image and answer a question with the vision model."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import socket
from typing import Any, TypeGuard
from urllib.parse import urljoin, urlparse

import httpx

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import resolve_virtual_path
from app.services.base_service.llm_service import LLMService
from app.services.base_service.model_resolver import resolve_scenario
from app.utils.logger import logger
from app.vfs.resolver import PathPermission

VISION_ANALYZE_DESCRIPTION = (
    "Analyze one image and answer a question about it. "
    "Only for images NOT already present as image content in the conversation: "
    "if the image is already attached to a message, analyze it directly with "
    "your own vision instead of calling this tool. "
    "image_url is required and must be exactly one of: an http or https URL, "
    "a virtual file path (for example /mnt/user-data/uploads/photo.png, or a "
    "path under workspace, outputs, or skills), or a "
    "data:image/(png|jpeg|gif|webp);base64,... URL. "
    "question is required and is the question or instruction about the image. "
    "Do not use read_file for images; call this tool instead."
)

_VISION_SYSTEM_PROMPT = (
    "你是图片分析助手。只根据给定图片和用户问题回答，"
    "不要编造图中不存在的内容。看不清或无法判断时直接说明。"
)

VISION_PASSTHROUGH_KIND = "vision_passthrough"

_VISION_GUIDANCE_PREFIX = (
    "下面是图片。请直接根据图片回答，不要编造图中不存在的内容。问题："
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 15.0
_MAX_REDIRECTS = 3
_REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})

_DATA_MIME_ALIASES = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class VisionAnalyzeTool(ToolBase):
    """Answer a question about an image using the vision scenario model."""

    name = "analyze"
    description = VISION_ANALYZE_DESCRIPTION

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        image_url = str(arguments.get("image_url") or "").strip()
        question = str(arguments.get("question") or "").strip()
        if not image_url:
            return ToolResult(content="Error: image_url is required", is_error=True)
        if not question:
            return ToolResult(content="Error: question is required", is_error=True)

        try:
            data_url = await load_image_data_url(
                image_url,
                user_id=ctx.user_id,
                conversation_id=ctx.conversation_id,
            )
        except (OSError, ValueError) as exc:
            logger.warning(
                "vision_analyze failed",
                source=_source_kind(image_url),
                error_type=type(exc).__name__,
            )
            return ToolResult(content=f"Error: {exc}", is_error=True)
        except Exception as exc:
            logger.error(
                "vision_analyze failed",
                source=_source_kind(image_url),
                error=exc,
            )
            return ToolResult(content=f"Error: {exc}", is_error=True)

        logger.info(
            "vision_analyze loaded image",
            source=_source_kind(image_url),
            data_url_chars=len(data_url),
        )
        return ToolResult(
            content=vision_passthrough_stub(question),
            structured_content=build_vision_passthrough_content(data_url, question),
        )


async def load_image_data_url(
    image_url: str,
    *,
    user_id: str,
    conversation_id: str,
) -> str:
    """Normalize http(s), virtual path, or data URL into a canonical data URL."""
    if image_url.startswith("data:"):
        return _data_url_from_data_url(image_url)
    if image_url.startswith(("http://", "https://")):
        return await fetch_remote_image(image_url)
    return _data_url_from_virtual_path(image_url, user_id, conversation_id)


async def fetch_remote_image(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Download a public http(s) image and return a canonical data URL."""
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    current = url
    try:
        for hop in range(_MAX_REDIRECTS + 1):
            await _assert_public_http_url(current)
            async with client.stream("GET", current) as response:
                if response.status_code in _REDIRECT_STATUS:
                    if hop == _MAX_REDIRECTS:
                        raise ValueError("image URL redirected too many times")
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("image URL redirect is missing a location")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise ValueError(
                        f"image download failed with status {response.status_code}"
                    )
                _reject_oversized_content_length(response)
                payload = await _read_limited(response)
                return _data_url_from_bytes(payload)
        raise ValueError("image URL redirected too many times")
    except httpx.HTTPError as exc:
        raise ValueError("image download failed") from exc
    finally:
        if owns_client:
            await client.aclose()


def detect_image_mime(payload: bytes) -> str | None:
    """Return a supported image MIME type from magic bytes, or None."""
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return None


def _data_url_from_virtual_path(
    virtual_path: str,
    user_id: str,
    conversation_id: str,
) -> str:
    physical_path = resolve_virtual_path(
        virtual_path,
        user_id,
        conversation_id,
        PathPermission.READ_ONLY,
    )
    if not physical_path.is_file():
        raise ValueError(f"{virtual_path} is not a file")
    size = physical_path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")
    if size == 0:
        raise ValueError("image file is empty")
    payload = physical_path.read_bytes()
    return _data_url_from_bytes(payload)


def _data_url_from_data_url(image_url: str) -> str:
    header, separator, encoded = image_url.partition(",")
    if separator != "," or not header.startswith("data:") or ";base64" not in header:
        raise ValueError("data URL must be a base64 image")
    declared = header[len("data:") :].split(";", 1)[0].strip().lower()
    mime = _DATA_MIME_ALIASES.get(declared)
    if mime is None:
        raise ValueError(
            "unsupported image type; only png, jpeg, gif, and webp are allowed"
        )
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("data URL is not valid base64") from exc
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")
    detected = detect_image_mime(payload)
    if detected != mime:
        raise ValueError("data URL content does not match its image type")
    return _canonical_data_url(mime, payload)


def _data_url_from_bytes(payload: bytes) -> str:
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")
    mime = detect_image_mime(payload)
    if mime is None:
        raise ValueError(
            "unsupported image type; only png, jpeg, gif, and webp are allowed"
        )
    return _canonical_data_url(mime, payload)


def _canonical_data_url(mime: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("image URL must be http or https")
    if parsed.username or parsed.password:
        raise ValueError("image URL must not include credentials")
    host = parsed.hostname
    if not host:
        raise ValueError("image URL is missing a host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = await _resolve_host_ips(host, port)
    if any(_is_blocked_ip(ip) for ip in addresses):
        raise ValueError("image URL host is not a public address")


async def _resolve_host_ips(
    host: str, port: int
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("image URL host could not be resolved") from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for *_, sockaddr in infos:
        raw_ip = str(sockaddr[0]).split("%", 1)[0]
        addresses.append(ipaddress.ip_address(raw_ip))
    if not addresses:
        raise ValueError("image URL host could not be resolved")
    return addresses


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _reject_oversized_content_length(response: httpx.Response) -> None:
    declared = response.headers.get("content-length")
    if declared is None:
        return
    try:
        size = int(declared)
    except ValueError:
        return
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")


async def _read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")
        chunks.append(chunk)
    if total == 0:
        raise ValueError("image download was empty")
    return b"".join(chunks)


def vision_passthrough_stub(question: str) -> str:
    """Short text persisted and shown for a vision passthrough result."""
    return f"图片已交给当前模型直接查看。问题：{question}"


def build_vision_passthrough_content(data_url: str, question: str) -> dict[str, str]:
    """Structured payload carrying pixels across the MCP text boundary."""
    return {
        "kind": VISION_PASSTHROUGH_KIND,
        "data_url": data_url,
        "question": question,
    }


def is_vision_passthrough(
    structured_content: Any,
) -> TypeGuard[dict[str, Any]]:
    """Whether an MCP structured payload is a loaded image awaiting routing."""
    if not isinstance(structured_content, dict):
        return False
    if structured_content.get("kind") != VISION_PASSTHROUGH_KIND:
        return False
    data_url = structured_content.get("data_url")
    return isinstance(data_url, str) and bool(data_url)


def build_vision_llm_content(data_url: str, question: str) -> list[dict[str, Any]]:
    """OpenAI-style tool content: guidance text plus the image."""
    return [
        {"type": "text", "text": f"{_VISION_GUIDANCE_PREFIX}{question}"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


async def ask_vision_model(question: str, data_url: str) -> str:
    llm_config = resolve_scenario("vision")
    service = LLMService(llm_config, think_mode=False)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    response = await service.call_llm_api(
        llm_config.model_name,
        messages,
        False,
        extra_body=service.extra_body,
    )
    raw = response.choices[0].message.content if response.choices else None
    return (raw or "").strip()


def _source_kind(image_url: str) -> str:
    if image_url.startswith("data:"):
        return "data_url"
    if image_url.startswith(("http://", "https://")):
        return "http"
    return "virtual_path"
