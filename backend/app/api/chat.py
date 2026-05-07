"""Chat endpoints for Q&A"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_mcp_manager
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.protocols.chat_messages import build_error_event
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import ChatRequest
from app.services.chat import ChatService
from app.services.message import MessageDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.logger import logger

router = APIRouter()
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


class _QueueSentinel:
    """Sentinel item for queue-draining completion."""


async def _run_producer(
    event_stream: AsyncGenerator[str, None],
    queue: asyncio.Queue[str | _QueueSentinel],
    sentinel: _QueueSentinel,
    log_ctx: dict[str, Any],
) -> None:
    try:
        async for event in event_stream:
            await queue.put(event)
    except asyncio.CancelledError:
        logger.info("Background chat producer cancelled", **log_ctx)
        raise
    except Exception as exc:
        logger.error(
            "Background chat producer failed",
            error=exc,
            error_type=type(exc).__name__,
            **log_ctx,
        )
        await queue.put(build_error_event({"content": str(exc)}))
    finally:
        await queue.put(sentinel)
        with contextlib.suppress(Exception):
            await event_stream.aclose()


async def _drain_queue(
    queue: asyncio.Queue[str | _QueueSentinel],
    sentinel: _QueueSentinel,
    log_ctx: dict[str, Any],
) -> AsyncGenerator[str, None]:
    try:
        while True:
            item = await queue.get()
            if isinstance(item, _QueueSentinel):
                return
            yield item
    except asyncio.CancelledError:
        logger.info("SSE consumer disconnected, producer continues", **log_ctx)
        return


def _run_detached_sse_stream(
    stream_factory: Callable[[], AsyncGenerator[str, None]],
    *,
    log_ctx: dict[str, Any],
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str | _QueueSentinel] = asyncio.Queue()
    sentinel = _QueueSentinel()
    producer_task = asyncio.create_task(
        _run_producer(
            event_stream=stream_factory(),
            queue=queue,
            sentinel=sentinel,
            log_ctx=log_ctx,
        ),
        name=f"chat_stream_producer_{log_ctx.get('assistant_message_id', 'unknown')}",
    )
    _BACKGROUND_TASKS.add(producer_task)

    def _on_producer_done(task: asyncio.Task[None]) -> None:
        _BACKGROUND_TASKS.discard(task)
        exception: BaseException | None = None
        if not task.cancelled():
            with contextlib.suppress(Exception):
                exception = task.exception()
        logger.info(
            "Background chat producer finished",
            exception=repr(exception) if exception else None,
            **log_ctx,
        )

    producer_task.add_done_callback(_on_producer_done)
    return _drain_queue(queue=queue, sentinel=sentinel, log_ctx=log_ctx)


@router.post("/stream")
async def stream_chat(
    chat_request: ChatRequest,
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> StreamingResponse:
    """Stream chat response, 按需保存用户与助手消息。user_id 用于 Mem0 记忆与 user_context 注入。"""
    logger.info(
        "Chat stream request received",
        chat_request=chat_request.model_dump(exclude_none=True),
    )
    logger.info(
        "Chat stream bootstrap",
        conversation_id=chat_request.conversation_id,
        user_id=auth_info.user_id,
    )

    user_metadata = chat_request.model_dump(
        exclude_none=True, exclude={"content_blocks"}
    )
    with MessageDbService() as message_service:
        created_messages = message_service.create_chat_messages(
            conversation_id=chat_request.conversation_id,
            content_blocks=chat_request.content_blocks,
            user_metadata=user_metadata,
            removed_message_ids=chat_request.removed_message_ids,
        )
    logger.info(
        "Messages created",
        conversation_id=chat_request.conversation_id,
        user_message_id=created_messages.user_message_id,
        assistant_message_id=created_messages.assistant_message_id,
    )

    chat_service = ChatService(
        think_mode=chat_request.think_mode,
        mcp_manager=mcp_manager,
        chat_context_config=settings.chat_context,
    )
    log_ctx = {
        "conversation_id": chat_request.conversation_id,
        "user_id": auth_info.user_id,
        "assistant_message_id": created_messages.assistant_message_id,
    }
    return StreamingResponse(
        _run_detached_sse_stream(
            lambda: chat_service.stream_chat_events(
                chat_request,
                created_messages.user_message_id,
                created_messages.assistant_message_id,
                user_id=auth_info.user_id,
            ),
            log_ctx=log_ctx,
        ),
        media_type="text/event-stream",
    )
