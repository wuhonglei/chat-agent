"""High-level chat streaming orchestrator."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Protocol

from app.agents import ChatSessionAgent, TitleGenerationAgent
from app.protocols.chat_messages import (
    build_ack_event,
    build_done_event,
    build_error_event,
    build_refresh_conversation_event,
    build_title_event,
)
from app.schemas.chat import (
    ChatMessageItem,
    ChatRequest,
    CollectedResponse,
    count_tool_use_blocks,
    extract_user_text,
)
from app.schemas.user import MemoryListItem
from app.services.chat.history_context_service import HistoryContextService
from app.services.chat.post_process_service import PostProcessService
from app.services.message import MessageDbService
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


class MemorySearch(Protocol):
    async def __call__(
        self,
        *,
        query: str,
        user_id: str,
    ) -> list[MemoryListItem]: ...


class ChatOrchestrator:
    """Coordinate the end-to-end chat response lifecycle."""

    def __init__(
        self,
        *,
        chat_session_agent: ChatSessionAgent,
        title_generation_agent: TitleGenerationAgent,
        history_context_service: HistoryContextService,
        post_process_service: PostProcessService,
    ) -> None:
        self.chat_session_agent = chat_session_agent
        self.title_generation_agent = title_generation_agent
        self.history_context_service = history_context_service
        self.post_process_service = post_process_service

    async def stream_message(
        self,
        chat_request: ChatRequest,
        window_out_summary: str | None,
        history_messages: list[ChatMessageItem],
        user_id: str,
        client_ip: str | None,
        user_memories: list[MemoryListItem] | None = None,
    ) -> AsyncGenerator[str, None]:
        logger.debug("user_memories", user_memories=user_memories)

        start_time = get_current_time()
        try:
            user_message = extract_user_text(chat_request.content_blocks)
            logger.info(
                "Starting chat message stream",
                user_message_length=len(user_message),
                history_messages_count=len(history_messages),
                client_ip=client_ip,
            )

            session_start_time = get_current_time()
            async for message in self.chat_session_agent.stream_execute(
                chat_request=chat_request,
                history_messages=history_messages,
                client_ip=client_ip,
                window_out_summary=window_out_summary,
                user_id=user_id,
                conversation_id=chat_request.conversation_id,
                user_memories=user_memories or [],
            ):
                yield message
            session_duration = get_time_duration(session_start_time)
            logger.debug(
                "Chat session agent execution completed",
                duration=session_duration,
                tool_calls_count=len(self.chat_session_agent.output_messages),
            )

            total_duration = get_time_duration(start_time)
            logger.info(
                "Chat message stream completed",
                total_duration=total_duration,
            )
            return

        except Exception as exc:
            total_duration = get_time_duration(start_time)
            logger.error(
                "Failed to stream message",
                error=exc,
                duration=total_duration,
            )
            yield build_error_event({"content": str(exc)})

    async def generate_title(
        self, user_message: str, conversation_id: str | None = None
    ) -> str:
        logger.info(
            "Regenerating conversation title",
            conversation_id=conversation_id,
        )
        title = await self.title_generation_agent.execute(user_message)
        logger.info(
            "Title generated",
            conversation_id=conversation_id,
            title=title,
            title_length=len(title) if title else 0,
        )
        return build_title_event({"id": conversation_id, "title": title})

    async def stream_response(
        self,
        *,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str,
        memory_search: MemorySearch,
    ) -> AsyncGenerator[str, None]:
        conversation_id = chat_request.conversation_id
        try:
            with MessageDbService() as message_service:
                conversation, user_message, assistant_message = (
                    message_service.get_conversation_and_messages(
                        conversation_id, user_message_id, assistant_message_id
                    )
                )
                logger.debug(
                    "Retrieved conversation and messages",
                    conversation_id=conversation_id,
                    user_message_role=user_message.role,
                    assistant_message_status=assistant_message.status,
                )

                yield build_ack_event(user_message)
                yield build_ack_event(assistant_message)
                yield build_refresh_conversation_event(conversation)

                title_task: asyncio.Task[str] | None = None
                user_message_text = extract_user_text(
                    chat_request.content_blocks)
                if chat_request.regenerate_title:
                    title_task = asyncio.create_task(
                        self.generate_title(
                            user_message_text,
                            conversation_id=conversation_id,
                        )
                    )

                raw_history = message_service.get_history_messages_by_ids(
                    chat_request.history_ids
                )
                (
                    window_out_summary,
                    new_history_messages,
                ) = await self.history_context_service.prepare_history_messages(
                    raw_history, conversation_id
                )
                logger.info(
                    "Starting stream message generation",
                    conversation_id=conversation_id,
                    history_ids_count=len(chat_request.history_ids),
                    history_messages_count=len(new_history_messages),
                )

                user_memory_texts = await memory_search(
                    query=user_message_text,
                    user_id=user_id,
                )

                chunk_count = 0
                async for chunk in self.stream_message(
                    chat_request=chat_request,
                    window_out_summary=window_out_summary,
                    history_messages=new_history_messages,
                    client_ip=None,
                    user_id=user_id,
                    user_memories=user_memory_texts,
                ):
                    if title_task is not None and title_task.done():
                        try:
                            if title_message := title_task.result():
                                yield title_message
                        except Exception:
                            pass
                        title_task = None
                    chunk_count += 1
                    yield chunk

                logger.info(
                    "Stream message generation completed",
                    conversation_id=conversation_id,
                    total_chunks=chunk_count,
                )

                assistant_payload = self.get_collected_response()
                assistant_updated_at = (
                    self.post_process_service.persist_assistant_response(
                        conversation_id=conversation_id,
                        user_message_id=user_message_id,
                        assistant_message_id=assistant_message_id,
                        assistant_payload=assistant_payload,
                    )
                )
                logger.info(
                    "Assistant message updated",
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_message_id,
                )

                done_payload = {
                    "content_length": len(assistant_payload.content),
                    "reasoning_length": len(assistant_payload.reasoning),
                    "tool_calls_length": count_tool_use_blocks(
                        assistant_payload.content_blocks
                    ),
                    "updated_at": str(assistant_updated_at),
                }
                logger.info(
                    "Sending done message",
                    conversation_id=conversation_id,
                    **done_payload,
                )
                yield build_done_event(done_payload)

                self.post_process_service.schedule_memory_persist(
                    chat_request=chat_request,
                    assistant_payload=assistant_payload,
                    user_id=user_id,
                )
        except Exception as exc:
            logger.error(
                "Error during stream response generation",
                conversation_id=conversation_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            yield build_error_event(
                {"content": str(exc), "conversation_id": conversation_id}
            )

    def get_collected_response(self) -> CollectedResponse:
        return CollectedResponse(
            content=self.chat_session_agent.content,
            reasoning=self.chat_session_agent.reasoning,
            content_blocks=self.chat_session_agent.content_blocks,
        )
