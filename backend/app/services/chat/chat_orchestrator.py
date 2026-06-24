"""High-level chat streaming orchestrator."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Coroutine
from contextlib import ExitStack
from typing import Any, Protocol, cast

from langfuse import propagate_attributes

from app.agents import ChatSessionAgent, TitleGenerationAgent
from app.core.observability import (
    get_langfuse,
    is_enabled,
    mark_observation_error,
    new_trace_id,
    observation_span,
)
from app.protocols.chat_messages import (
    build_ack_event,
    build_done_event,
    build_error_event,
    build_refresh_conversation_event,
    build_title_event,
)
from app.schemas.chat import (
    AssistantResponse,
    ChatMessage,
    ChatRequest,
    ContentBlock,
    KbContextBlock,
    MessageStatus,
    count_tool_use_blocks,
    extract_user_text,
)
from app.schemas.user import MemorySearchItem
from app.services.chat.errors import ChatStreamError
from app.services.chat.history_context_service import HistoryContextService
from app.services.chat.kb_rag_context_service import KbRagContextService
from app.services.chat.post_process_service import PostProcessService
from app.services.message import MessageDbService
from app.utils.logger import logger
from app.utils.multimodal import (
    collect_attachment_content_ids,
    collect_attachment_content_ids_from_history_messages,
    extract_user_text_with_attachment_placeholder,
)
from app.utils.time import get_current_time, get_time_duration


async def _merge_stream_with_title_task(
    stream: AsyncGenerator[str, None],
    title_task: asyncio.Task[str] | None,
    *,
    conversation_id: str | None,
) -> AsyncGenerator[str, None]:
    """Interleave stream events with the title event as soon as either completes.

    Unlike polling ``title_task.done()`` after each stream chunk, this avoids delaying
    the title event until the next chunk arrives when the title finishes first.
    """
    if title_task is None:
        async for event in stream:
            yield event
        return

    aiter = stream.__aiter__()
    next_chunk: asyncio.Task[str] = asyncio.create_task(
        cast(Coroutine[Any, Any, str], aiter.__anext__())
    )
    pending_title: asyncio.Task[str] | None = title_task
    stream_ended = False

    try:
        while True:
            wait_set = {next_chunk}
            if pending_title is not None:
                wait_set.add(pending_title)
            done, _ = await asyncio.wait(
                wait_set,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if pending_title is not None and pending_title in done:
                try:
                    if title_event := pending_title.result():
                        yield title_event
                except Exception as exc:
                    logger.warning(
                        "Failed to emit title event during stream",
                        conversation_id=conversation_id,
                        error=exc,
                        error_type=type(exc).__name__,
                    )
                pending_title = None

            if next_chunk in done:
                try:
                    event = next_chunk.result()
                except StopAsyncIteration:
                    stream_ended = True
                    break
                yield event
                next_chunk = asyncio.create_task(
                    cast(Coroutine[Any, Any, str], aiter.__anext__())
                )
    finally:
        if not next_chunk.done():
            next_chunk.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await next_chunk
        if not stream_ended and pending_title is not None and not pending_title.done():
            pending_title.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending_title

    if stream_ended and pending_title is not None:
        try:
            if title_event := await pending_title:
                yield title_event
        except Exception as exc:
            logger.warning(
                "Failed to emit title event after stream completed",
                conversation_id=conversation_id,
                error=exc,
                error_type=type(exc).__name__,
            )


class MemorySearch(Protocol):
    async def __call__(
        self,
        *,
        query: str,
        user_id: str,
    ) -> list[MemorySearchItem]: ...


class ChatOrchestrator:
    """Coordinate the end-to-end chat response lifecycle."""

    def __init__(
        self,
        *,
        chat_session_agent: ChatSessionAgent,
        title_generation_agent: TitleGenerationAgent,
        history_context_service: HistoryContextService,
        post_process_service: PostProcessService,
        kb_rag_context_service: KbRagContextService,
    ) -> None:
        self.chat_session_agent = chat_session_agent
        self.title_generation_agent = title_generation_agent
        self.history_context_service = history_context_service
        self.post_process_service = post_process_service
        self.kb_rag_context_service = kb_rag_context_service

    async def stream_turn_events(
        self,
        chat_request: ChatRequest,
        history_summary_before_window: str | None,
        history_messages: list[ChatMessage],
        user_id: str,
        user_memories: list[MemorySearchItem] | None = None,
        kb_context_blocks: list[KbContextBlock] | None = None,
    ) -> AsyncGenerator[str, None]:
        logger.debug("user_memories", user_memories=user_memories)

        start_time = get_current_time()
        try:
            user_message = extract_user_text(chat_request.content_blocks)
            logger.info(
                "Starting chat message stream",
                user_message_length=len(user_message),
                history_messages_count=len(history_messages),
            )

            session_start_time = get_current_time()
            async for event in self.chat_session_agent.stream_session_events(
                chat_request=chat_request,
                history_messages=history_messages,
                history_summary_before_window=history_summary_before_window,
                conversation_id=chat_request.conversation_id,
                user_memories=user_memories or [],
                user_id=user_id,
                kb_context_blocks=kb_context_blocks,
            ):
                yield event
            session_duration = get_time_duration(session_start_time)
            logger.debug(
                "Chat session agent execution completed",
                duration=session_duration,
                tool_calls_count=len(self.chat_session_agent.tool_round_messages),
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
            raise ChatStreamError(str(exc)) from exc

    async def generate_title_event(
        self,
        user_message: str | list[ContentBlock] | list[dict[str, Any]],
        kb_context_blocks: list[KbContextBlock],
        conversation_id: str | None = None,
    ) -> str:
        title_start_time = get_current_time()
        logger.info(
            "Regenerating conversation title",
            conversation_id=conversation_id,
        )
        with observation_span(
            "title-generation",
            input={"conversation_id": conversation_id},
        ) as title_span:
            try:
                title = await self.title_generation_agent.execute(
                    user_message=user_message,
                    kb_context_blocks=kb_context_blocks,
                )
            except Exception as exc:
                mark_observation_error(title_span, exc)
                logger.error(
                    "Failed to generate title",
                    conversation_id=conversation_id,
                    error=exc,
                    error_type=type(exc).__name__,
                    duration=get_time_duration(title_start_time),
                )
                raise
            if title_span is not None:
                title_span.update(
                    output={
                        "title": title,
                        "title_length": len(title) if title else 0,
                    }
                )
        logger.info(
            "Title generated",
            conversation_id=conversation_id,
            title=title,
            title_length=len(title) if title else 0,
            duration=get_time_duration(title_start_time),
        )
        return build_title_event({"id": conversation_id, "title": title})

    async def run_chat_turn(
        self,
        *,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str,
        memory_search: MemorySearch,
    ) -> AsyncGenerator[str, None]:
        conversation_id = chat_request.conversation_id
        trace_enabled = is_enabled()
        langfuse_client = get_langfuse()
        assistant_response: AssistantResponse | None = None
        try:
            with ExitStack() as trace_stack:
                root_span: Any = None
                if trace_enabled and langfuse_client is not None:
                    try:
                        root_span = trace_stack.enter_context(
                            langfuse_client.start_as_current_observation(
                                as_type="span",
                                name="chat-turn",
                                trace_context={
                                    "trace_id": new_trace_id(assistant_message_id)
                                },
                            )
                        )
                        trace_stack.enter_context(
                            propagate_attributes(
                                user_id=user_id,
                                session_id=conversation_id,
                                trace_name="chat-turn",
                                metadata={
                                    key: str(value)
                                    for key, value in {
                                        "conversation_id": conversation_id,
                                        "user_message_id": user_message_id,
                                        "assistant_message_id": assistant_message_id,
                                        "model_id": chat_request.model_id,
                                        "agent_mode": chat_request.agent_mode,
                                        "client_turn_id": chat_request.client_turn_id,
                                    }.items()
                                    if value is not None
                                },
                            )
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to start Langfuse trace span",
                            error=exc,
                            error_type=type(exc).__name__,
                            conversation_id=conversation_id,
                        )
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

                    event_count = 0
                    try:
                        history_messages_from_db = (
                            message_service.get_history_messages_by_ids(
                                chat_request.history_ids
                            )
                        )
                        with observation_span(
                            "history-prepare",
                            input={
                                "history_ids_count": len(chat_request.history_ids),
                            },
                        ) as history_span:
                            try:
                                (
                                    history_summary_before_window,
                                    prepared_history_messages,
                                ) = await self.history_context_service.prepare_history_messages(
                                    history_messages_from_db, conversation_id
                                )
                            except Exception as exc:
                                mark_observation_error(history_span, exc)
                                raise
                            if history_span is not None:
                                history_span.update(
                                    output={
                                        "prepared_count": len(
                                            prepared_history_messages
                                        ),
                                        "has_window_summary": bool(
                                            history_summary_before_window
                                        ),
                                    }
                                )
                        logger.info(
                            "Starting stream message generation",
                            conversation_id=conversation_id,
                            history_ids_count=len(chat_request.history_ids),
                            history_messages_count=len(prepared_history_messages),
                        )

                        user_message_text = (
                            extract_user_text_with_attachment_placeholder(
                                chat_request.content_blocks
                            )
                        )
                        if (
                            trace_enabled
                            and langfuse_client is not None
                            and root_span is not None
                        ):
                            try:
                                root_span.update(input=user_message_text)
                            except Exception as exc:
                                logger.warning(
                                    "Failed to update Langfuse trace input",
                                    error=exc,
                                    error_type=type(exc).__name__,
                                    conversation_id=conversation_id,
                                )

                        user_memories = await memory_search(
                            query=user_message_text,
                            user_id=user_id,
                        )
                        with observation_span(
                            "kb-rag-build",
                            input={
                                "query": user_message_text,
                                "candidate_content_ids_count": len(
                                    collect_attachment_content_ids(
                                        chat_request.content_blocks
                                    )
                                ),
                            },
                        ) as kb_span:
                            try:
                                kb_context_blocks = await self._build_kb_context_blocks(
                                    content_blocks=chat_request.content_blocks,
                                    history_messages=prepared_history_messages,
                                    user_id=user_id,
                                    user_message_text=user_message_text,
                                )
                            except Exception as exc:
                                mark_observation_error(kb_span, exc)
                                raise
                            if kb_span is not None:
                                kb_span.update(
                                    output={
                                        "block_count": len(kb_context_blocks or []),
                                    }
                                )
                        if chat_request.regenerate_title:
                            title_task = asyncio.create_task(
                                self.generate_title_event(
                                    chat_request.content_blocks,
                                    kb_context_blocks=kb_context_blocks or [],
                                    conversation_id=conversation_id,
                                )
                            )

                        async for event in _merge_stream_with_title_task(
                            self.stream_turn_events(
                                chat_request=chat_request,
                                history_summary_before_window=history_summary_before_window,
                                history_messages=prepared_history_messages,
                                user_id=user_id,
                                user_memories=user_memories,
                                kb_context_blocks=kb_context_blocks,
                            ),
                            title_task,
                            conversation_id=conversation_id,
                        ):
                            event_count += 1
                            yield event
                    except asyncio.CancelledError:
                        # 流式中断时，content_block_aggregator 已累积当前轮的数据，
                        # 但 session_output.content_blocks 还没同步 — 手动同步后再收集。
                        self.chat_session_agent._sync_session_output()
                        assistant_response = self.collect_assistant_response()
                        message_service.update_assistant_message(
                            conversation,
                            assistant_message,
                            assistant_response=assistant_response,
                            status=MessageStatus.STOPPED,
                        )
                        if (
                            trace_enabled
                            and langfuse_client is not None
                            and root_span is not None
                        ):
                            try:
                                root_span.update(
                                    output=assistant_response.content,
                                    metadata={"status": MessageStatus.STOPPED.value},
                                )
                            except Exception as exc:
                                logger.warning(
                                    "Failed to update stopped trace status",
                                    error=exc,
                                    error_type=type(exc).__name__,
                                    conversation_id=conversation_id,
                                )
                        raise
                    except ChatStreamError as exc:
                        # 主会话流式失败：error 事件已下发，这里只做失败收尾——
                        # 落库 FAILED、trace 标 ERROR，并跳过 done 与记忆写入。
                        self.chat_session_agent._sync_session_output()
                        assistant_response = self.collect_assistant_response()
                        message_service.update_assistant_message(
                            conversation,
                            assistant_message,
                            assistant_response=assistant_response,
                            status=MessageStatus.FAILED,
                        )
                        if (
                            trace_enabled
                            and langfuse_client is not None
                            and root_span is not None
                        ):
                            try:
                                root_span.update(
                                    level="ERROR",
                                    status_message=type(exc).__name__,
                                    output=assistant_response.content,
                                    metadata={"status": MessageStatus.FAILED.value},
                                )
                            except Exception as update_exc:
                                logger.warning(
                                    "Failed to update failed trace status",
                                    error=update_exc,
                                    error_type=type(update_exc).__name__,
                                    conversation_id=conversation_id,
                                )
                        return
                    finally:
                        if title_task is not None and not title_task.done():
                            title_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await title_task

                    logger.info(
                        "Stream message generation completed",
                        conversation_id=conversation_id,
                        total_events=event_count,
                    )

                    assistant_response = self.collect_assistant_response()
                    assistant_updated_at = (
                        self.post_process_service.persist_final_assistant_message(
                            conversation_id=conversation_id,
                            user_message_id=user_message_id,
                            assistant_message_id=assistant_message_id,
                            assistant_response=assistant_response,
                        )
                    )
                    logger.info(
                        "Assistant message updated",
                        conversation_id=conversation_id,
                        assistant_message_id=assistant_message_id,
                    )
                    if (
                        trace_enabled
                        and langfuse_client is not None
                        and root_span is not None
                    ):
                        try:
                            root_span.update(output=assistant_response.content)
                        except Exception as exc:
                            logger.warning(
                                "Failed to update Langfuse root span output",
                                error=exc,
                                error_type=type(exc).__name__,
                                conversation_id=conversation_id,
                            )

                    done_event_payload = {
                        "content_length": len(assistant_response.content),
                        "reasoning_length": len(assistant_response.reasoning),
                        "tool_calls_length": count_tool_use_blocks(
                            assistant_response.content_blocks
                        ),
                        "updated_at": str(assistant_updated_at),
                    }
                    logger.info(
                        "Sending done message",
                        conversation_id=conversation_id,
                        **done_event_payload,
                    )
                    yield build_done_event(done_event_payload)

            # memory-write 通过 asyncio.create_task 异步执行，不在 Langfuse 中单独建 trace，
            # 避免与 chat-turn 共用 trace_id 时出现两条 traces。
            if assistant_response is not None:
                self.post_process_service.schedule_memory_write(
                    chat_request=chat_request,
                    assistant_response=assistant_response,
                    user_id=user_id,
                )
        except Exception as exc:
            logger.error(
                "Error during stream response generation",
                conversation_id=conversation_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            if trace_enabled and langfuse_client is not None:
                try:
                    langfuse_client.update_current_span(
                        level="ERROR",
                        status_message=type(exc).__name__,
                    )
                except Exception as update_exc:
                    logger.warning(
                        "Failed to mark trace observation as error",
                        error=update_exc,
                        error_type=type(update_exc).__name__,
                        conversation_id=conversation_id,
                    )
            yield build_error_event(
                {"content": str(exc), "conversation_id": conversation_id}
            )

    def collect_assistant_response(self) -> AssistantResponse:
        return AssistantResponse(
            content=self.chat_session_agent.content,
            reasoning=self.chat_session_agent.reasoning,
            content_blocks=self.chat_session_agent.content_blocks,
        )

    async def _build_kb_context_blocks(
        self,
        *,
        content_blocks: list[ContentBlock],
        history_messages: list[ChatMessage],
        user_id: str,
        user_message_text: str,
    ) -> list[KbContextBlock] | None:
        current_turn_content_ids = collect_attachment_content_ids(content_blocks)
        current_turn_has_attachment = bool(current_turn_content_ids)
        if current_turn_has_attachment:
            # 当前轮已上传附件时，优先绑定本轮附件，避免历史附件干扰检索。
            candidate_content_ids = current_turn_content_ids
        else:
            candidate_content_ids = (
                collect_attachment_content_ids_from_history_messages(history_messages)
            )
        return await self.kb_rag_context_service.build_context_block_content(
            user_id=user_id,
            query_text=user_message_text,
            candidate_content_ids=candidate_content_ids,
            current_turn_has_attachment=current_turn_has_attachment,
            content_blocks=content_blocks,
            history_messages=history_messages,
        )
