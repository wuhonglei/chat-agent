"""对话列表游标分页服务测试（SQLite 内存库）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.conversation_db import ConversationDb
from app.models.user import UserDb
from app.schemas.conversation import CreatedBy
from app.services.conversation.conversation_db import ConversationDbService
from app.utils.cursor import InvalidCursorError, encode_conversation_cursor

ID_A = "00000000-0000-4000-8000-00000000000a"
ID_B = "00000000-0000-4000-8000-00000000000b"
ID_C = "00000000-0000-4000-8000-00000000000c"
ID_D = "00000000-0000-4000-8000-00000000000d"
ID_0 = "00000000-0000-4000-8000-000000000000"
ID_1 = "00000000-0000-4000-8000-000000000001"
ID_2 = "00000000-0000-4000-8000-000000000002"
ID_3 = "00000000-0000-4000-8000-000000000003"
ID_4 = "00000000-0000-4000-8000-000000000004"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(
        engine, tables=[UserDb.__table__, ConversationDb.__table__]
    )
    with Session(engine) as session:
        user = UserDb(id="user-1", name="tester", email="t@example.com")
        session.add(user)
        session.commit()
        yield session


def _add_conversation(
    session: Session,
    *,
    conversation_id: str,
    last_message_created_at: datetime,
    title: str | None = None,
    is_active: bool = True,
    user_id: str = "user-1",
) -> ConversationDb:
    conv = ConversationDb(
        id=conversation_id,
        title=title or conversation_id,
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


def test_first_page_has_more_and_next_cursor(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    for i, cid in enumerate([ID_0, ID_1, ID_2, ID_3, ID_4]):
        _add_conversation(
            db_session,
            conversation_id=cid,
            last_message_created_at=base + timedelta(minutes=i),
        )

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=2)

    assert len(page.conversations) == 2
    assert page.has_more is True
    assert page.next_cursor is not None
    assert len(page.next_cursor) == 32
    assert page.limit == 2
    # 最新在前：ID_4, ID_3
    assert [c.id for c in page.conversations] == [ID_4, ID_3]


def test_cursor_pages_have_no_overlap_or_gaps(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    # 同一时间戳多条，验证 id 打破并列
    same_ts = base
    _add_conversation(db_session, conversation_id=ID_A, last_message_created_at=same_ts)
    _add_conversation(db_session, conversation_id=ID_B, last_message_created_at=same_ts)
    _add_conversation(db_session, conversation_id=ID_C, last_message_created_at=same_ts)
    _add_conversation(
        db_session,
        conversation_id=ID_D,
        last_message_created_at=base + timedelta(minutes=1),
    )

    service = ConversationDbService(db_session)
    page1 = service.get_conversations_paginated("user-1", limit=2)
    assert page1.has_more is True
    assert page1.next_cursor is not None
    ids1 = [c.id for c in page1.conversations]

    page2 = service.get_conversations_paginated(
        "user-1", cursor=page1.next_cursor, limit=2
    )
    ids2 = [c.id for c in page2.conversations]

    assert set(ids1).isdisjoint(ids2)
    # 时间更新的 ID_D 在前；同时间按 id DESC：C, B, A
    assert ids1 + ids2 == [ID_D, ID_C, ID_B, ID_A]
    assert page2.has_more is False
    assert page2.next_cursor is None


def test_last_page_has_no_more(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(db_session, conversation_id=ID_A, last_message_created_at=base)

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=20)
    assert len(page.conversations) == 1
    assert page.has_more is False
    assert page.next_cursor is None


def test_inactive_conversations_excluded(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(db_session, conversation_id=ID_A, last_message_created_at=base)
    _add_conversation(
        db_session,
        conversation_id=ID_B,
        last_message_created_at=base + timedelta(minutes=1),
        is_active=False,
    )

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=20)
    assert [c.id for c in page.conversations] == [ID_A]


def test_invalid_cursor_raises(db_session: Session) -> None:
    service = ConversationDbService(db_session)
    with pytest.raises(InvalidCursorError):
        service.get_conversations_paginated("user-1", cursor="not-a-cursor", limit=10)


def test_cursor_continues_after_deleted_anchor(db_session: Session) -> None:
    """游标指向已删除行时，仍应按 keyset 继续向前，不卡死。"""
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    for i, cid in enumerate([ID_A, ID_B, ID_C]):
        _add_conversation(
            db_session,
            conversation_id=cid,
            last_message_created_at=base + timedelta(minutes=i),
        )

    # 模拟「B」被删除后，仍用 B 的游标续页
    ghost_cursor = encode_conversation_cursor(base + timedelta(minutes=1), ID_B)
    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated(
        "user-1", cursor=ghost_cursor, limit=10
    )
    assert [c.id for c in page.conversations] == [ID_A]
