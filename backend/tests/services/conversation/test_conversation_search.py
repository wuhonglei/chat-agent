"""会话搜索服务测试（SQLite 内存库）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.conversation_db import ConversationDb
from app.models.message_db import MessageDb
from app.models.user import UserDb
from app.schemas.conversation import ConversationSearchMatchType, CreatedBy
from app.services.conversation.conversation_db import ConversationDbService

ID_A = "00000000-0000-4000-8000-00000000000a"
ID_B = "00000000-0000-4000-8000-00000000000b"
ID_C = "00000000-0000-4000-8000-00000000000c"
MSG_1 = "00000000-0000-4000-8000-0000000000m1"
MSG_2 = "00000000-0000-4000-8000-0000000000m2"
MSG_3 = "00000000-0000-4000-8000-0000000000m3"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[UserDb.__table__, ConversationDb.__table__, MessageDb.__table__],
    )
    with Session(engine) as session:
        session.add(UserDb(id="user-1", name="tester", email="t@example.com"))
        session.add(UserDb(id="user-2", name="other", email="o@example.com"))
        session.commit()
        yield session


def _add_conversation(
    session: Session,
    *,
    conversation_id: str,
    last_message_created_at: datetime,
    title: str,
    is_active: bool = True,
    user_id: str = "user-1",
) -> ConversationDb:
    conv = ConversationDb(
        id=conversation_id,
        title=title,
        created_by=CreatedBy.DEFAULT,
        user_id=user_id,
        is_active=is_active,
        last_message_created_at=last_message_created_at,
        last_message_updated_at=last_message_created_at,
        created_at=last_message_created_at,
        updated_at=last_message_created_at,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def _add_message(
    session: Session,
    *,
    message_id: str,
    conversation_id: str,
    role: str,
    text: str,
    created_at: datetime,
    status: str = "done",
) -> MessageDb:
    msg = MessageDb(
        id=message_id,
        conversation_id=conversation_id,
        role=role,
        content_blocks=[{"id": f"{message_id}-t", "type": "text", "text": text}],
        content_text=text,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg


def test_search_by_title(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="调研 DigiFinex 公司",
    )
    _add_conversation(
        db_session,
        conversation_id=ID_B,
        last_message_created_at=base + timedelta(minutes=1),
        title="天气怎么样",
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="调研", limit=20)

    assert len(page.conversations) == 1
    assert page.conversations[0].id == ID_A
    assert page.conversations[0].match_type == ConversationSearchMatchType.TITLE
    assert page.has_more is False


def test_search_by_user_and_assistant_message(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="普通会话",
    )
    _add_conversation(
        db_session,
        conversation_id=ID_B,
        last_message_created_at=base + timedelta(minutes=1),
        title="另一会话",
    )
    _add_message(
        db_session,
        message_id=MSG_1,
        conversation_id=ID_A,
        role="user",
        text="Please research DigiFinex company",
        created_at=base,
    )
    _add_message(
        db_session,
        message_id=MSG_2,
        conversation_id=ID_B,
        role="assistant",
        text="Here is the DigiFinex research report",
        created_at=base + timedelta(minutes=1),
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="DigiFinex", limit=20)

    assert {item.id for item in page.conversations} == {ID_A, ID_B}
    by_id = {item.id: item for item in page.conversations}
    assert by_id[ID_A].match_type == ConversationSearchMatchType.USER
    assert "DigiFinex" in by_id[ID_A].snippet
    assert by_id[ID_B].match_type == ConversationSearchMatchType.ASSISTANT
    assert "DigiFinex" in by_id[ID_B].snippet


def test_search_by_chinese_message_content(db_session: Session) -> None:
    """content_text 冗余列后，中文正文可直接 ILIKE 命中（不依赖 JSON 序列化）。"""
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="普通会话",
    )
    _add_message(
        db_session,
        message_id=MSG_1,
        conversation_id=ID_A,
        role="user",
        text="请帮我调研一下 DigiFinex 公司",
        created_at=base,
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="调研", limit=20)

    assert len(page.conversations) == 1
    assert page.conversations[0].id == ID_A
    assert page.conversations[0].match_type == ConversationSearchMatchType.USER
    assert "调研" in page.conversations[0].snippet


def test_search_prefers_title_over_message(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="调研 DigiFinex",
    )
    _add_message(
        db_session,
        message_id=MSG_1,
        conversation_id=ID_A,
        role="user",
        text="帮我调研一下",
        created_at=base,
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="调研", limit=20)

    assert len(page.conversations) == 1
    assert page.conversations[0].match_type == ConversationSearchMatchType.TITLE
    assert page.conversations[0].snippet == ""


def test_search_isolates_by_user(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="调研 A",
        user_id="user-1",
    )
    _add_conversation(
        db_session,
        conversation_id=ID_B,
        last_message_created_at=base + timedelta(minutes=1),
        title="调研 B",
        user_id="user-2",
    )
    _add_message(
        db_session,
        message_id=MSG_3,
        conversation_id=ID_B,
        role="user",
        text="调研内容仅属于 user-2",
        created_at=base + timedelta(minutes=1),
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="调研", limit=20)

    assert [item.id for item in page.conversations] == [ID_A]


def test_search_skips_inactive_and_pending_messages(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(
        db_session,
        conversation_id=ID_A,
        last_message_created_at=base,
        title="活跃会话",
    )
    _add_conversation(
        db_session,
        conversation_id=ID_B,
        last_message_created_at=base + timedelta(minutes=1),
        title="DigiFinex 草稿",
        is_active=False,
    )
    _add_conversation(
        db_session,
        conversation_id=ID_C,
        last_message_created_at=base + timedelta(minutes=2),
        title="pending 消息会话",
    )
    _add_message(
        db_session,
        message_id=MSG_1,
        conversation_id=ID_C,
        role="user",
        text="Contains DigiFinex keyword",
        created_at=base + timedelta(minutes=2),
        status="pending",
    )

    service = ConversationDbService(db_session)
    page = service.search_conversations("user-1", q="DigiFinex", limit=20)

    assert page.conversations == []
