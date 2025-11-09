"""Chat endpoints for Q&A"""

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.chat import ChatRequest, MessageStatus
from app.services.chat_service import ChatService
from app.models.app_state import AppState
from app.services.message_service import MessageService
from app.utils.common import gen_uuid

router = APIRouter()


@router.post("/stream")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
):
    """Stream chat response, 按需保存用户与助手消息"""
    conversation_id = chat_request.conversation_id
    state = cast(AppState, request.app.state)

    chat_service = ChatService(mcp_manager=state.mcp_manager)

    user_metadata = {
        "mcp_auto_mode": chat_request.mcp_auto_mode,
        "think_mode": chat_request.think_mode,
        "history_size": len(chat_request.history),
        "regenerate_title": chat_request.regenerate_title,
        "source_config": chat_request.source_config.model_dump(exclude_none=True),
    }

    try:
        user_message_id = gen_uuid()
        assistant_message_id = gen_uuid()
        with MessageService() as message_service:
            conversation = message_service.get_conversation(conversation_id)
            user_message = message_service.create_user_message(
                conversation=conversation,
                message_id=user_message_id,
                content=chat_request.message,
                metadata={**user_metadata,
                          "reply_message_id": assistant_message_id},
            )
            assistant_message = message_service.create_assistant_message(
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
            # 立即返回 ack，提示前端消息已入库
            yield chat_service._format_sse_message('ack', user_message)
            yield chat_service._format_sse_message('ack', assistant_message)
            yield chat_service._format_sse_message('refresh_conversation', conversation)

            try:
                async for chunk in chat_service.stream_message(
                    chat_request=chat_request
                ):
                    yield chunk
            except Exception as streaming_error:
                logger.error(f"Streaming response failed: {streaming_error}")
                raise

            assistant_payload = chat_service.get_collected_response()
            tool_call_details = assistant_payload.tool_calls
            assistant_metadata = {
                "mcp_auto_mode": chat_request.mcp_auto_mode,
                "think_mode": chat_request.think_mode,
                "tool_call_count": len(tool_call_details) if tool_call_details else 0,
            }

            try:
                message_service.update_assistant_message(
                    assistant_message_id,
                    content=assistant_payload.content,
                    reasoning=assistant_payload.reasoning,
                    tool_calls=assistant_payload.tool_calls,
                    status=MessageStatus.DONE,
                    extra_metadata=assistant_metadata,
                )
            except Exception as persist_error:
                logger.error(
                    f"Failed to persist assistant message: {persist_error}")
                raise

        if chat_request.regenerate_title:
            title = await chat_service.generate_title(chat_request.message)
            yield chat_service._format_sse_message('title', {
                'id': conversation_id,
                'title': title
            })

        yield chat_service._format_sse_message('done')
        return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
