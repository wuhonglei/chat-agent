"""Commit ordering and invalidation tests for business write paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.api import chat as chat_api
from app.api import conversation as conversation_api
from app.api import message as message_api
from app.models import ConversationDb, MessageDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import MessageFeedbackValue
from app.schemas.conversation import CreatedBy, UpdateConversationRequest


def _token(user_id: str = "user-1") -> AuthTokenPayload:
    return AuthTokenPayload(user_id=user_id, iat=1, exp=2)


@pytest.mark.asyncio
async def test_update_conversation_commits_before_invalidation() -> None:
    db = MagicMock(spec=Session)
    db.get.return_value = ConversationDb(
        id="conv-1",
        title="Old",
        user_id="user-1",
    )

    async def assert_committed(*_args: object) -> None:
        db.commit.assert_called_once()

    invalidate = AsyncMock(side_effect=assert_committed)
    with patch(
        "app.api.conversation.invalidate_conversation",
        new=invalidate,
    ):
        response = await conversation_api.update_conversation(
            "conv-1",
            UpdateConversationRequest(
                id="conv-1",
                title="New",
                created_by=CreatedBy.USER,
            ),
            db=db,
            token_info=_token(),
        )

    assert response.data is not None
    assert response.data.title == "New"
    invalidate.assert_awaited_once_with("conv-1", "user-1")


@pytest.mark.asyncio
async def test_delete_message_commits_before_invalidation() -> None:
    db = MagicMock(spec=Session)
    message = MessageDb(
        id="msg-1",
        conversation_id="conv-1",
        role="user",
    )
    conversation = ConversationDb(
        id="conv-1",
        title="Title",
        user_id="user-1",
    )
    db.get.side_effect = [message, conversation]

    async def assert_committed(*_args: object) -> None:
        db.commit.assert_called_once()

    invalidate = AsyncMock(side_effect=assert_committed)
    with patch("app.api.message.invalidate_messages", new=invalidate):
        response = await message_api.delete_message(
            "msg-1",
            db=db,
            token_info=_token(),
        )

    assert response.data == "msg-1"
    invalidate.assert_awaited_once_with("conv-1")


@pytest.mark.asyncio
async def test_feedback_commits_before_full_conversation_invalidation() -> None:
    db = MagicMock(spec=Session)
    message = MessageDb(
        id="msg-1",
        conversation_id="conv-1",
        role="assistant",
    )
    conversation = ConversationDb(
        id="conv-1",
        title="Title",
        user_id="user-1",
    )
    db.get.side_effect = [message, conversation]

    async def assert_committed(*_args: object) -> None:
        db.commit.assert_called_once()

    invalidate = AsyncMock(side_effect=assert_committed)
    with patch(
        "app.api.message.invalidate_conversation_state",
        new=invalidate,
    ):
        response = await message_api.update_message_feedback(
            "msg-1",
            message_api.UpdateMessageFeedbackRequest(value=MessageFeedbackValue.LIKE),
            db=db,
            token_info=_token(),
        )

    assert response.code == 0
    invalidate.assert_awaited_once_with("conv-1", "user-1")


@pytest.mark.asyncio
async def test_create_chat_turn_invalidates_after_service_context_commit() -> None:
    context = MagicMock()
    service = MagicMock()
    context.__enter__.return_value = service
    service.create_chat_messages.return_value = SimpleNamespace(
        user_message_id="user-msg-1",
        assistant_message_id="assistant-msg-1",
    )

    async def assert_context_exited(*_args: object) -> None:
        context.__exit__.assert_called_once()

    invalidate = AsyncMock(side_effect=assert_context_exited)
    with (
        patch("app.api.chat.MessageDbService", return_value=context),
        patch(
            "app.api.chat.invalidate_conversation_state",
            new=invalidate,
        ),
    ):
        result = await chat_api._create_chat_turn(
            conversation_id="conv-1",
            user_id="user-1",
            content_blocks=[],
            user_metadata={},
            removed_message_ids=None,
        )

    assert result.user_message_id == "user-msg-1"
    invalidate.assert_awaited_once_with("conv-1", "user-1")


@pytest.mark.asyncio
async def test_create_chat_turn_invalidates_after_partial_write_failure() -> None:
    context = MagicMock()
    service = MagicMock()
    context.__enter__.return_value = service
    service.create_chat_messages.side_effect = RuntimeError("second write failed")
    invalidate = AsyncMock()

    with (
        patch("app.api.chat.MessageDbService", return_value=context),
        patch(
            "app.api.chat.invalidate_conversation_state",
            new=invalidate,
        ),
        pytest.raises(RuntimeError, match="second write failed"),
    ):
        await chat_api._create_chat_turn(
            conversation_id="conv-1",
            user_id="user-1",
            content_blocks=[],
            user_metadata={},
            removed_message_ids=None,
        )

    invalidate.assert_awaited_once_with("conv-1", "user-1")


def test_chat_stream_rejects_conversation_owned_by_another_user() -> None:
    context = MagicMock()
    service = MagicMock()
    context.__enter__.return_value = service
    service.get_conversation.return_value = ConversationDb(
        id="conv-1",
        title="Other user's conversation",
        user_id="user-1",
    )

    with (
        patch("app.api.chat.MessageDbService", return_value=context),
        pytest.raises(HTTPException) as exc_info,
    ):
        chat_api._ensure_owned_conversation(
            conversation_id="conv-1",
            auth_info=_token("user-2"),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_conversation_write_rejects_wrong_owner_without_commit() -> None:
    db = MagicMock(spec=Session)
    db.get.return_value = ConversationDb(
        id="conv-1",
        title="Title",
        user_id="user-1",
    )

    response = await conversation_api.update_conversation(
        "conv-1",
        UpdateConversationRequest(
            id="conv-1",
            title="Forbidden",
            created_by=CreatedBy.USER,
        ),
        db=db,
        token_info=_token("user-2"),
    )

    assert response.code == 404
    db.commit.assert_not_called()
