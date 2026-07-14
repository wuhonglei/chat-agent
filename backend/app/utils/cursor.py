"""Opaque cursor helpers for keyset pagination."""

from __future__ import annotations

import base64
import struct
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID

# 8-byte big-endian int64 microseconds + 16-byte UUID
_CURSOR_BINARY_LEN = 24
_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ConversationListCursor(NamedTuple):
    last_message_created_at: datetime
    id: str


class InvalidCursorError(ValueError):
    """Raised when a pagination cursor cannot be decoded."""


def _datetime_to_micros(value: datetime) -> int:
    if value.tzinfo is None:
        utc = value.replace(tzinfo=timezone.utc)
    else:
        utc = value.astimezone(timezone.utc)
    delta = utc - _EPOCH_UTC
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _micros_to_datetime(micros: int) -> datetime:
    return datetime.fromtimestamp(micros / 1_000_000, tz=timezone.utc)


def encode_conversation_cursor(
    last_message_created_at: datetime, conversation_id: str
) -> str:
    """Encode list cursor as URL-safe Base64 of packed (micros, uuid)."""
    try:
        uuid_bytes = UUID(conversation_id).bytes
    except ValueError as exc:
        raise InvalidCursorError("无效的 conversation id") from exc

    raw = struct.pack(">q", _datetime_to_micros(last_message_created_at)) + uuid_bytes
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_conversation_cursor(cursor: str) -> ConversationListCursor:
    """Decode and validate a conversation list cursor."""
    if not cursor or not cursor.strip():
        raise InvalidCursorError("无效的 cursor")

    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("无效的 cursor") from exc

    if len(raw) != _CURSOR_BINARY_LEN:
        raise InvalidCursorError("无效的 cursor")

    try:
        micros = struct.unpack(">q", raw[:8])[0]
        conversation_id = str(UUID(bytes=raw[8:]))
    except (struct.error, ValueError) as exc:
        raise InvalidCursorError("无效的 cursor") from exc

    return ConversationListCursor(
        last_message_created_at=_micros_to_datetime(micros),
        id=conversation_id,
    )
