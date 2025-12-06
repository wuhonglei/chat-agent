"""Chat endpoints for Q&A"""

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from fastapi import Depends
from app.models.chat import ChatRequest, MessageStatus
from app.services.chat_service import ChatService
from app.models.app_state import AppState
from app.services.message_service import MessageService
from app.models.db import MessageDb
from app.utils.auth_deps import require_auth
from app.utils.common import gen_uuid
from app.utils.time import get_current_time, get_time_duration
router = APIRouter()


@router.post("/stream")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    _auth: None = Depends(require_auth)
):
    """Stream chat response, 按需保存用户与助手消息"""
    conversation_id = chat_request.conversation_id
    state = cast(AppState, request.app.state)

    chat_service = ChatService(mcp_manager=state.mcp_manager)

    user_metadata = chat_request.model_dump(
        exclude_none=True, exclude=['content'])

    try:
        user_message_id = gen_uuid()
        assistant_message_id = gen_uuid()
        with MessageService() as message_service:
            conversation = message_service.get_conversation(conversation_id)
            message_service.remove_messages(chat_request.removed_message_ids)
            message_service.create_user_message(
                conversation=conversation,
                message_id=user_message_id,
                content=chat_request.content,
                metadata={**user_metadata,
                          "reply_message_id": assistant_message_id},
            )
            message_service.create_assistant_message(
                conversation=conversation,
                message_id=assistant_message_id,
                reply_to=user_message_id,
                metadata=user_metadata,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to persist user message: {exc}")
        raise HTTPException(status_code=500, detail="用户消息写入失败") from exc

    async def generate() -> AsyncGenerator[str, None]:
        with MessageService() as message_service:
            conversation = message_service.get_conversation(conversation_id)
            user_message = message_service.db.get(MessageDb, user_message_id)
            assistant_message = message_service.db.get(
                MessageDb, assistant_message_id)

            # 立即返回 ack，提示前端消息已入库
            yield chat_service.format_sse_message('ack', user_message)
            yield chat_service.format_sse_message('ack', assistant_message)
            yield chat_service.format_sse_message('refresh_conversation', conversation)
            start_time = get_current_time()
            try:
                history = message_service.get_flatten_messages_by_ids(
                    chat_request.history_ids)
                async for chunk in chat_service.stream_message(
                    chat_request=chat_request,
                    history=history
                ):
                    yield chunk
            except Exception as streaming_error:
                logger.error(f"Streaming response failed: {streaming_error}")
                raise
            chat_service.total_duration = get_time_duration(start_time)
            assistant_payload = chat_service.get_collected_response()

            try:
                assistant_message = message_service.update_assistant_message(
                    conversation,
                    assistant_message,
                    assistant_payload=assistant_payload,
                    status=MessageStatus.DONE,
                )
            except Exception as persist_error:
                logger.error(
                    f"Failed to persist assistant message: {persist_error}")
                yield chat_service.format_sse_message('error', {'msg': str(persist_error)})
                raise

            if chat_request.regenerate_title:
                title = await chat_service.generate_title(chat_request.content)
                yield chat_service.format_sse_message('title', {
                    'id': conversation_id,
                    'title': title
                })

            yield chat_service.format_sse_message('done', {'last_message_updated_at': assistant_message.updated_at.isoformat()})

        return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
