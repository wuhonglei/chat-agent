"""对话列表游标编解码单元测试。"""

import base64
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.utils.cursor import (
    InvalidCursorError,
    decode_conversation_cursor,
    encode_conversation_cursor,
)


def test_encode_decode_roundtrip() -> None:
    ts = datetime(2026, 7, 14, 9, 30, 0, 544192, tzinfo=timezone.utc)
    conversation_id = "72491fb4-3a82-452d-985b-b09ff93af98d"
    cursor = encode_conversation_cursor(ts, conversation_id)
    assert len(cursor) == 32
    decoded = decode_conversation_cursor(cursor)
    assert decoded.id == conversation_id
    assert decoded.last_message_created_at == ts


def test_encode_preserves_non_utc_instant() -> None:
    from datetime import timedelta

    plus8 = timezone(timedelta(hours=8))
    local_plus8 = datetime(2026, 6, 23, 17, 28, 23, 544192, tzinfo=plus8)
    utc = local_plus8.astimezone(timezone.utc)
    conversation_id = "72491fb4-3a82-452d-985b-b09ff93af98d"

    cursor_local = encode_conversation_cursor(local_plus8, conversation_id)
    cursor_utc = encode_conversation_cursor(utc, conversation_id)
    assert cursor_local == cursor_utc
    assert len(cursor_local) == 32

    decoded = decode_conversation_cursor(cursor_local)
    assert decoded.last_message_created_at == utc
    assert decoded.id == conversation_id


def test_encode_rejects_invalid_uuid() -> None:
    ts = datetime(2026, 7, 14, 9, 30, 0, tzinfo=timezone.utc)
    with pytest.raises(InvalidCursorError):
        encode_conversation_cursor(ts, "not-a-uuid")


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "   ",
        "not-base64!!!",
        # 错误长度（旧 JSON cursor 或截断）
        base64.urlsafe_b64encode(b"short").decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(b"\x00" * 23).decode("ascii").rstrip("="),
        # 24 字节但 UUID 非法（全 0 其实合法）；构造无效：改用错误长度更稳
        base64.urlsafe_b64encode(b"\x00" * 25).decode("ascii").rstrip("="),
    ],
)
def test_decode_invalid_cursor(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_conversation_cursor(cursor)


def test_decode_accepts_valid_packed_bytes() -> None:
    ts = datetime(2026, 7, 14, 9, 30, 0, tzinfo=timezone.utc)
    conversation_id = "72491fb4-3a82-452d-985b-b09ff93af98d"
    cursor = encode_conversation_cursor(ts, conversation_id)
    # 带 padding 也应可解
    padded = cursor + "=" * (-len(cursor) % 4)
    decoded = decode_conversation_cursor(padded)
    assert decoded.id == str(UUID(conversation_id))
