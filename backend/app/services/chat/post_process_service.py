"""Post-processing helpers for chat streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.schemas.chat import (
    AssistantResponse,
    ChatRequest,
    MessageStatus,
    extract_user_text,
)
from app.services.message import MessageDbService
from app.services.user.memory_service import MemoryService


class PostProcessService:
    """Persist final assistant payloads and schedule memory writes."""

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    def persist_final_assistant_message(
        self,
        *,
        conversation_id: str,
        user_message_id: str,
        assistant_message_id: str,
        assistant_response: AssistantResponse,
    ) -> datetime:
        with MessageDbService() as message_service:
            conversation, _, assistant_message = (
                message_service.get_conversation_and_messages(
                    conversation_id, user_message_id, assistant_message_id
                )
            )
            assistant_message = message_service.update_assistant_message(
                conversation,
                assistant_message,
                assistant_response=assistant_response,
                status=MessageStatus.DONE,
            )
            return assistant_message.updated_at

    def schedule_memory_write(
        self,
        *,
        chat_request: ChatRequest,
        assistant_response: AssistantResponse,
        user_id: str,
    ) -> None:
        asyncio.create_task(
            self.memory_service.add_memories(
                messages=[
                    {
                        "role": "user",
                        "content": extract_user_text(chat_request.content_blocks),
                    },
                    {
                        "role": "assistant",
                        "content": assistant_response.content or "",
                    },
                ],
                user_id=user_id,
                run_id=chat_request.conversation_id,
            ),
            name="mem0_add_memories",
        )
