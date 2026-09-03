"""消息列表 API 剥离 llm_rendered_text。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from app.services.conversation.conversation_db import ConversationDbService


class _FakeMessage:
    def __init__(self, *, message_id: str, metadata: dict[str, Any]) -> None:
        self.id = message_id
        self.conversation_id = "c1"
        self.role = "user"
        self.content_blocks = [{"id": "t1", "type": "text", "text": "hello"}]
        self.created_at = datetime(2026, 9, 3, 4, 0, 0, tzinfo=timezone.utc)
        self.updated_at = self.created_at
        self.message_metadata = metadata
        self.status = "done"
        self.reply_to = None
        self.feedback = None

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content_blocks": self.content_blocks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_metadata": dict(self.message_metadata),
            "status": self.status,
            "reply_to": self.reply_to,
            "feedback": self.feedback,
        }


def test_get_messages_strips_llm_rendered_text() -> None:
    service = ConversationDbService(db=MagicMock())
    fake_msg = _FakeMessage(
        message_id="u1",
        metadata={
            "llm_rendered_text": "<user_message>secret prompt</user_message>",
            "user_memories": [{"memory": "喜欢喝茶"}],
            "agent_mode": 0,
        },
    )
    db = MagicMock()
    db.exec.return_value.all.return_value = [fake_msg]
    service._ensure_db = MagicMock(return_value=db)  # type: ignore[method-assign]

    payloads = service.get_messages("c1")
    assert len(payloads) == 1
    metadata = payloads[0]["message_metadata"]
    assert "llm_rendered_text" not in metadata
    assert metadata["user_memories"][0]["memory"] == "喜欢喝茶"
    assert metadata["agent_mode"] == 0
    # 原始 DB 对象不应被就地改写
    assert "llm_rendered_text" in fake_msg.message_metadata
