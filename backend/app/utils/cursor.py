"""Opaque cursor helpers for keyset pagination."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import NamedTuple


class ConversationListCursor(NamedTuple):
    last_message_created_at: datetime
    id: str


class InvalidCursorError(ValueError):
    """Raised when a pagination cursor cannot be decoded."""


def encode_conversation_cursor(
    last_message_created_at: datetime, conversation_id: str
) -> str:
    """Encode list cursor as URL-safe Base64 JSON."""
    payload = {
        "t": last_message_created_at.isoformat(),
        "i": conversation_id,
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_conversation_cursor(cursor: str) -> ConversationListCursor:
    """Decode and validate a conversation list cursor."""
    if not cursor or not cursor.strip():
        raise InvalidCursorError("无效的 cursor")

    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("无效的 cursor") from exc

    if not isinstance(payload, dict):
        raise InvalidCursorError("无效的 cursor")

    timestamp_raw = payload.get("t")
    conversation_id = payload.get("i")
    if (
        not isinstance(timestamp_raw, str)
        or not timestamp_raw
        or not isinstance(conversation_id, str)
        or not conversation_id
    ):
        raise InvalidCursorError("无效的 cursor")

    try:
        timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidCursorError("无效的 cursor") from exc

    return ConversationListCursor(
        last_message_created_at=timestamp,
        id=conversation_id,
    )
