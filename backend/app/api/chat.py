"""Chat endpoints for Q&A"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_mcp_manager
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.protocols.chat_messages import build_error_event
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import (
    ChatRequest,
    MessageStatus,
    StreamResumeRequest,
    StreamStopRequest,
)
from app.schemas.config import LLMConfig
from app.schemas.response import ApiResponse
from app.services.chat import ChatService
from app.services.chat.stream_relay import StreamRelay
from app.services.message import MessageDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.logger import logger

router = APIRouter()
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_STREAM_RELAY = StreamRelay()
_STREAM_PRODUCER_TASKS: dict[str, asyncio.Task[None]] = {}
_TURN_IDEMPOTENCY_LOCK = asyncio.Lock()
_TURN_IDEMPOTENCY_CACHE: dict[tuple[str, str, str], "_IdempotentTurn"] = {}


@dataclass(frozen=True)
class _IdempotentTurn:
    user_message_id: str
    assistant_message_id: str


async def _run_producer(
    event_stream: AsyncGenerator[str, None],
    stream_id: str,
    log_ctx: dict[str, Any],
) -> None:
    try:
        async for event in event_stream:
            await _STREAM_RELAY.append(stream_id, event)
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
        await _STREAM_RELAY.append(stream_id, build_error_event({"content": str(exc)}))
    finally:
        await _STREAM_RELAY.close(stream_id)
        with contextlib.suppress(Exception):
            await event_stream.aclose()


async def _drain_stream(
    stream_id: str,
    *,
    last_event_id: int,
    log_ctx: dict[str, Any],
) -> AsyncGenerator[str, None]:
    try:
        async for event in _STREAM_RELAY.iter_resume(
            stream_id, last_event_id=last_event_id
        ):
            yield event
    except asyncio.CancelledError:
        logger.info("SSE consumer disconnected, producer continues", **log_ctx)
        return


async def _run_detached_sse_stream(
    stream_factory: Callable[[], AsyncGenerator[str, None]],
    *,
    stream_id: str,
    log_ctx: dict[str, Any],
) -> AsyncGenerator[str, None]:
    await _STREAM_RELAY.register(stream_id)
    producer_task = asyncio.create_task(
        _run_producer(
            event_stream=stream_factory(),
            stream_id=stream_id,
            log_ctx=log_ctx,
        ),
        name=f"chat_stream_producer_{log_ctx.get('assistant_message_id', 'unknown')}",
    )
    _BACKGROUND_TASKS.add(producer_task)
    _STREAM_PRODUCER_TASKS[stream_id] = producer_task

    def _on_producer_done(task: asyncio.Task[None]) -> None:
        _BACKGROUND_TASKS.discard(task)
        _STREAM_PRODUCER_TASKS.pop(stream_id, None)
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
    return _drain_stream(stream_id=stream_id, last_event_id=0, log_ctx=log_ctx)


async def _empty_stream() -> AsyncGenerator[str, None]:
    return
    yield  # pragma: no cover


def _ensure_authorized_assistant_message(
    *,
    assistant_message_id: str,
    auth_info: AuthTokenPayload,
) -> None:
    with MessageDbService() as message_service:
        message = message_service.get_message(assistant_message_id)
        if message is None or message.role != "assistant":
            raise HTTPException(status_code=404, detail="助手消息不存在")
        conversation = message_service.get_conversation(message.conversation_id)
        if conversation.user_id != auth_info.user_id:
            raise HTTPException(status_code=403, detail="无权访问该消息")


def _resolve_llm_config(model_id: str) -> LLMConfig:
    if model_id == "default":
        return settings.model_map["default"]

    llm_config = settings.model_map.get(model_id)
    if llm_config is not None:
        return llm_config

    return settings.model_map["default"]


def _contains_image_block(chat_request: ChatRequest) -> bool:
    return any(block.type == "image" for block in chat_request.content_blocks)


def _parse_last_event_id(last_event_id: str | None) -> int:
    if not last_event_id:
        return 0
    try:
        parsed = int(last_event_id)
    except ValueError:
        return 0
    return max(parsed, 0)


def _idempotency_key(
    *,
    user_id: str,
    conversation_id: str,
    client_turn_id: str | None,
) -> tuple[str, str, str] | None:
    if not client_turn_id:
        return None
    return (user_id, conversation_id, client_turn_id)


@router.post("/stream")
async def stream_chat(
    chat_request: ChatRequest,
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
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
    llm_config = _resolve_llm_config(chat_request.model_id)
    if _contains_image_block(chat_request) and not llm_config.image_support:
        raise HTTPException(status_code=400, detail="当前模型不支持图片输入")

    last_event_id = _parse_last_event_id(last_event_id_header)
    user_metadata = chat_request.model_dump(
        exclude_none=True, exclude={"content_blocks"}
    )
    idempotency_key = _idempotency_key(
        user_id=auth_info.user_id,
        conversation_id=chat_request.conversation_id,
        client_turn_id=chat_request.client_turn_id,
    )
    created_messages: _IdempotentTurn
    is_idempotent_hit = False
    async with _TURN_IDEMPOTENCY_LOCK:
        cached_turn = (
            _TURN_IDEMPOTENCY_CACHE.get(idempotency_key)
            if idempotency_key is not None
            else None
        )
        if cached_turn is not None:
            created_messages = cached_turn
            is_idempotent_hit = True
        else:
            with MessageDbService() as message_service:
                db_created_messages = message_service.create_chat_messages(
                    conversation_id=chat_request.conversation_id,
                    content_blocks=chat_request.content_blocks,
                    user_metadata=user_metadata,
                    removed_message_ids=chat_request.removed_message_ids,
                )
            created_messages = _IdempotentTurn(
                user_message_id=db_created_messages.user_message_id,
                assistant_message_id=db_created_messages.assistant_message_id,
            )
            if idempotency_key is not None:
                _TURN_IDEMPOTENCY_CACHE[idempotency_key] = created_messages
    logger.info(
        "Messages resolved",
        conversation_id=chat_request.conversation_id,
        user_message_id=created_messages.user_message_id,
        assistant_message_id=created_messages.assistant_message_id,
        client_turn_id=chat_request.client_turn_id,
        idempotent_hit=is_idempotent_hit,
    )

    chat_service = ChatService(
        think_mode=chat_request.think_mode,
        llm_config=llm_config,
        mcp_manager=mcp_manager,
        chat_context_config=settings.chat_context,
    )
    log_ctx = {
        "conversation_id": chat_request.conversation_id,
        "user_id": auth_info.user_id,
        "assistant_message_id": created_messages.assistant_message_id,
        "last_event_id": last_event_id,
    }
    if is_idempotent_hit:
        if await _STREAM_RELAY.has_stream(created_messages.assistant_message_id):
            return StreamingResponse(
                _drain_stream(
                    stream_id=created_messages.assistant_message_id,
                    last_event_id=last_event_id,
                    log_ctx=log_ctx,
                ),
                media_type="text/event-stream",
            )
        return StreamingResponse(
            _empty_stream(),
            media_type="text/event-stream",
        )

    stream = await _run_detached_sse_stream(
        lambda: chat_service.stream_chat_events(
            chat_request,
            created_messages.user_message_id,
            created_messages.assistant_message_id,
            user_id=auth_info.user_id,
        ),
        stream_id=created_messages.assistant_message_id,
        log_ctx=log_ctx,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
    )


@router.post("/stream/resume")
async def resume_chat_stream(
    request: StreamResumeRequest,
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    _ensure_authorized_assistant_message(
        assistant_message_id=request.assistant_message_id,
        auth_info=auth_info,
    )

    last_event_id = _parse_last_event_id(last_event_id_header)

    if not await _STREAM_RELAY.has_stream(request.assistant_message_id):
        logger.info(
            "Resume requested for inactive stream",
            assistant_message_id=request.assistant_message_id,
            user_id=auth_info.user_id,
            last_event_id=last_event_id,
        )
        return StreamingResponse(
            _empty_stream(),
            media_type="text/event-stream",
        )

    log_ctx = {
        "assistant_message_id": request.assistant_message_id,
        "user_id": auth_info.user_id,
        "resume_last_event_id": last_event_id,
    }
    return StreamingResponse(
        _drain_stream(
            stream_id=request.assistant_message_id,
            last_event_id=last_event_id,
            log_ctx=log_ctx,
        ),
        media_type="text/event-stream",
    )


@router.post("/stream/stop")
async def stop_chat_stream(
    request: StreamStopRequest,
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[dict[str, bool]]:
    _ensure_authorized_assistant_message(
        assistant_message_id=request.assistant_message_id,
        auth_info=auth_info,
    )

    producer_task = _STREAM_PRODUCER_TASKS.get(request.assistant_message_id)
    if producer_task and not producer_task.done():
        producer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer_task

    with MessageDbService() as message_service:
        assistant_message = message_service.get_message(request.assistant_message_id)
        if assistant_message is None:
            return ApiResponse.success(data={"stopped": True}, msg="流式响应已停止")
        if assistant_message.status == MessageStatus.PENDING:
            conversation = message_service.get_conversation(
                assistant_message.conversation_id
            )
            message_service.update_assistant_message_status(
                conversation,
                assistant_message,
                status=MessageStatus.STOPPED,
            )

    logger.info(
        "Chat stream stopped by user",
        assistant_message_id=request.assistant_message_id,
        user_id=auth_info.user_id,
    )
    return ApiResponse.success(data={"stopped": True}, msg="流式响应已停止")
