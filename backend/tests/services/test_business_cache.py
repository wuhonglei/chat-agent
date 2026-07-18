"""Cache-Aside tests for user and conversation read services."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.conversation_db import ConversationDb
from app.models.user import UserDb
from app.services.conversation.conversation_db import ConversationDbService
from app.services.user.user_db import UserDbService


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[UserDb.__table__, ConversationDb.__table__],
    )
    with Session(engine) as session:
        session.add(UserDb(id="user-1", name="Tester", email="t@example.com"))
        session.add(
            ConversationDb(
                id="conv-1",
                title="Cached conversation",
                user_id="user-1",
            )
        )
        session.commit()
        yield session


@pytest.mark.asyncio
async def test_user_detail_miss_loads_db_and_backfills(db_session: Session) -> None:
    l2_set = AsyncMock(return_value=True)
    with (
        patch(
            "app.services.user.user_db.l2_get",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.user.user_db.l2_set", new=l2_set),
    ):
        user = await UserDbService(db_session).get_or_load_user_detail("user-1")

    assert user is not None
    assert user.name == "Tester"
    l2_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_detail_hit_skips_db() -> None:
    db = MagicMock(spec=Session)
    cached = UserDb(id="user-1", name="Cached", email=None).model_dump(mode="json")
    with patch(
        "app.services.user.user_db.l2_get",
        new=AsyncMock(return_value=cached),
    ):
        user = await UserDbService(db).get_or_load_user_detail("user-1")

    assert user is not None
    assert user.name == "Cached"
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_detail_miss_backfills_owned_envelope(
    db_session: Session,
) -> None:
    l2_set = AsyncMock(return_value=True)
    with (
        patch(
            "app.services.conversation.conversation_db.l2_get",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.conversation.conversation_db.l2_set",
            new=l2_set,
        ),
    ):
        detail = await ConversationDbService(db_session).get_or_load_conversation_info(
            "conv-1", "user-1"
        )

    assert detail is not None
    assert detail.id == "conv-1"
    envelope = l2_set.await_args.args[1]
    assert envelope["owner_user_id"] == "user-1"


@pytest.mark.asyncio
async def test_conversation_detail_wrong_owner_does_not_query_db() -> None:
    db = MagicMock(spec=Session)
    cached = {
        "owner_user_id": "user-1",
        "response": {
            "id": "conv-1",
            "title": "Title",
            "created_by": "default",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    with patch(
        "app.services.conversation.conversation_db.l2_get",
        new=AsyncMock(return_value=cached),
    ):
        detail = await ConversationDbService(db).get_or_load_conversation_info(
            "conv-1", "user-2"
        )

    assert detail is None
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_list_hit_restores_response_model() -> None:
    db = MagicMock(spec=Session)
    cached = {
        "conversations": [],
        "next_cursor": None,
        "has_more": False,
        "limit": 20,
    }
    with patch(
        "app.services.conversation.conversation_db.l2_get",
        new=AsyncMock(return_value=cached),
    ):
        result = await ConversationDbService(db).get_or_load_conversations_paginated(
            "user-1", limit=20
        )

    assert result.conversations == []
    assert result.limit == 20
    db.exec.assert_not_called()


@pytest.mark.asyncio
async def test_messages_hit_enforces_owner() -> None:
    db = MagicMock(spec=Session)
    cached = {
        "owner_user_id": "user-1",
        "response": {
            "total": 0,
            "offset": 0,
            "limit": 0,
            "messages": [],
        },
    }
    with patch(
        "app.services.conversation.conversation_db.l2_get",
        new=AsyncMock(return_value=cached),
    ):
        service = ConversationDbService(db)
        allowed = await service.get_or_load_messages("conv-1", "user-1")
        denied = await service.get_or_load_messages("conv-1", "user-2")

    assert allowed is not None
    assert allowed["total"] == 0
    assert denied is None
    db.get.assert_not_called()
