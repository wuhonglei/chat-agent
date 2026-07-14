"""对话列表游标编解码单元测试。"""

import base64
import json
from datetime import datetime, timezone

import pytest

from app.utils.cursor import (
    InvalidCursorError,
    decode_conversation_cursor,
    encode_conversation_cursor,
)


def _b64_json(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_encode_decode_roundtrip() -> None:
    ts = datetime(2026, 7, 14, 9, 30, 0, tzinfo=timezone.utc)
    conversation_id = "conv-abc-123"
    cursor = encode_conversation_cursor(ts, conversation_id)
    decoded = decode_conversation_cursor(cursor)
    assert decoded.id == conversation_id
    assert decoded.last_message_created_at == ts


def test_decode_accepts_zulu_timestamp() -> None:
    cursor = _b64_json({"t": "2026-07-14T09:30:00Z", "i": "conv-1"})
    decoded = decode_conversation_cursor(cursor)
    assert decoded.id == "conv-1"
    assert decoded.last_message_created_at == datetime(
        2026, 7, 14, 9, 30, 0, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "   ",
        "not-base64!!!",
        _b64_json({}),
        _b64_json({"t": "2026-07-14T09:30:00+00:00"}),
        _b64_json({"t": "not-a-time", "i": "x"}),
    ],
)
def test_decode_invalid_cursor(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_conversation_cursor(cursor)
