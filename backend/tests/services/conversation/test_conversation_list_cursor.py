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


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine, tables=[UserDb.__table__, ConversationDb.__table__])
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
    for i in range(5):
        _add_conversation(
            db_session,
            conversation_id=f"c{i}",
            last_message_created_at=base + timedelta(minutes=i),
        )

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=2)

    assert len(page.conversations) == 2
    assert page.has_more is True
    assert page.next_cursor is not None
    assert page.limit == 2
    # 最新在前：c4, c3
    assert [c.id for c in page.conversations] == ["c4", "c3"]


def test_cursor_pages_have_no_overlap_or_gaps(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    # 同一时间戳多条，验证 id 打破并列
    same_ts = base
    _add_conversation(db_session, conversation_id="a", last_message_created_at=same_ts)
    _add_conversation(db_session, conversation_id="b", last_message_created_at=same_ts)
    _add_conversation(db_session, conversation_id="c", last_message_created_at=same_ts)
    _add_conversation(
        db_session,
        conversation_id="d",
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
    assert ids1 + ids2 == ["d", "c", "b", "a"]
    assert page2.has_more is False
    assert page2.next_cursor is None


def test_last_page_has_no_more(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(db_session, conversation_id="only", last_message_created_at=base)

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=20)
    assert len(page.conversations) == 1
    assert page.has_more is False
    assert page.next_cursor is None


def test_inactive_conversations_excluded(db_session: Session) -> None:
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    _add_conversation(db_session, conversation_id="active", last_message_created_at=base)
    _add_conversation(
        db_session,
        conversation_id="draft",
        last_message_created_at=base + timedelta(minutes=1),
        is_active=False,
    )

    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated("user-1", limit=20)
    assert [c.id for c in page.conversations] == ["active"]


def test_invalid_cursor_raises(db_session: Session) -> None:
    service = ConversationDbService(db_session)
    with pytest.raises(InvalidCursorError):
        service.get_conversations_paginated("user-1", cursor="not-a-cursor", limit=10)


def test_cursor_continues_after_deleted_anchor(db_session: Session) -> None:
    """游标指向已删除行时，仍应按 keyset 继续向前，不卡死。"""
    base = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    for i, cid in enumerate(["a", "b", "c"]):
        _add_conversation(
            db_session,
            conversation_id=cid,
            last_message_created_at=base + timedelta(minutes=i),
        )

    # 模拟「b」被删除后，仍用 b 的游标续页
    ghost_cursor = encode_conversation_cursor(base + timedelta(minutes=1), "b")
    service = ConversationDbService(db_session)
    page = service.get_conversations_paginated(
        "user-1", cursor=ghost_cursor, limit=10
    )
    assert [c.id for c in page.conversations] == ["a"]
