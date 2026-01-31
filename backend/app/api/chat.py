"""Chat endpoints for Q&A"""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.mcp.mcp_client import MCPClientManager
from app.models import MessageDb
from app.schemas.chat import ChatRequest, MessageStatus
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.utils.auth_deps import require_auth
from app.utils.common import pick_fields
from app.utils.logger import logger
from app.utils.model import format_sse_message
from app.utils.time import get_current_time, get_time_duration

router = APIRouter()


def get_mcp_manager(request: Request) -> MCPClientManager:
    """获取 MCP Manager 依赖注入函数"""
    return cast(MCPClientManager, request.app.state.mcp_manager)


@router.post("/stream")
async def chat_stream(
    chat_request: ChatRequest,
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
    _auth: None = Depends(require_auth),
) -> StreamingResponse:
    """Stream chat response, 按需保存用户与助手消息"""
    logger.info(
        "Chat stream request received",
        chat_request=chat_request.model_dump(exclude_none=True),
    )

    user_metadata = chat_request.model_dump(exclude_none=True, exclude={"content"})

    # 创建用户消息和助手消息
    with MessageService() as message_service:
        messages_result = message_service.create_chat_messages(
            conversation_id=chat_request.conversation_id,
            content=chat_request.content,
            user_metadata=user_metadata,
            removed_message_ids=chat_request.removed_message_ids,
        )
        user_message_id = messages_result.user_message_id
        assistant_message_id = messages_result.assistant_message_id
        logger.info(
            "Messages created",
            conversation_id=chat_request.conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )

    async def generate() -> AsyncGenerator[str, None]:
        """生成流式响应"""
        logger.info(
            "Starting stream response generation",
            conversation_id=chat_request.conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )
        try:
            with MessageService() as message_service:
                conversation = message_service.get_conversation(
                    chat_request.conversation_id
                )
                user_message = message_service.session.get(MessageDb, user_message_id)
                assistant_message = message_service.session.get(
                    MessageDb, assistant_message_id
                )
                if user_message is None or assistant_message is None:
                    raise ValueError(
                        f"Message not found: user={user_message_id}, assistant={assistant_message_id}"
                    )

                logger.debug(
                    "Retrieved conversation and messages",
                    conversation_id=chat_request.conversation_id,
                    user_message_role=user_message.role if user_message else None,
                    assistant_message_status=assistant_message.status
                    if assistant_message
                    else None,
                )

                # 发送初始确认消息
                logger.debug("Sending initial acknowledgment messages")
                yield format_sse_message("ack", user_message)
                yield format_sse_message("ack", assistant_message)
                yield format_sse_message("refresh_conversation", conversation)
                logger.debug("Initial acknowledgment messages sent")

                chat_service = ChatService(
                    think_mode=chat_request.think_mode, mcp_manager=mcp_manager
                )
                logger.debug(
                    "ChatService created",
                    conversation_id=chat_request.conversation_id,
                    think_mode=chat_request.think_mode,
                )

                # 如需重新生成标题则异步执行，不阻塞正文流
                title_task: asyncio.Task[str] | None = None
                if chat_request.regenerate_title:
                    title_task = asyncio.create_task(
                        chat_service.generate_title(
                            chat_request.content,
                            conversation_id=chat_request.conversation_id,
                        )
                    )

                # 流式生成响应
                start_time = get_current_time()
                history_messages = message_service.get_history_messages_by_ids(
                    chat_request.history_ids
                )
                logger.info(
                    "Starting stream message generation",
                    conversation_id=chat_request.conversation_id,
                    history_ids_count=len(chat_request.history_ids),
                    history_messages_count=len(history_messages),
                )

                chunk_count = 0
                async for chunk in chat_service.stream_message(
                    chat_request=chat_request,
                    history_messages=history_messages,
                    client_ip=None,
                ):
                    # 若标题已生成则先下发，再下发正文 chunk
                    if title_task is not None and title_task.done():
                        try:
                            if title_message := title_task.result():
                                yield title_message
                        except Exception:
                            pass
                        title_task = None
                    chunk_count += 1
                    yield chunk

                # 若标题任务尚未完成，等待后下发
                if title_task is not None:
                    try:
                        if title_message := await title_task:
                            yield title_message
                    except Exception as e:
                        logger.warning(
                            "Title generation failed, stream continues",
                            conversation_id=chat_request.conversation_id,
                            error=e,
                        )

                logger.info(
                    "Stream message generation completed",
                    conversation_id=chat_request.conversation_id,
                    total_chunks=chunk_count,
                )

                # 更新助手消息
                total_duration = get_time_duration(start_time)
                assistant_payload = chat_service.get_collected_response()

                logger.debug(
                    "Collected assistant response",
                    conversation_id=chat_request.conversation_id,
                    content_length=len(assistant_payload.content),
                    reasoning_length=len(assistant_payload.reasoning),
                    tool_calls_count=len(assistant_payload.tool_calls),
                    component_tool_calls_count=len(
                        assistant_payload.component_tool_calls
                    ),
                    total_duration=total_duration,
                )

                assistant_message = message_service.update_assistant_message(
                    conversation,
                    assistant_message,
                    assistant_payload=assistant_payload,
                    status=MessageStatus.DONE,
                )

                logger.info(
                    "Assistant message updated",
                    conversation_id=chat_request.conversation_id,
                    assistant_message_id=assistant_message_id,
                    status=MessageStatus.DONE,
                    updated_at=str(assistant_message.updated_at)
                    if assistant_message.updated_at
                    else None,
                )

                # 发送完成消息
                done_payload = {
                    "content_length": len(assistant_payload.content),
                    "reasoning_length": len(assistant_payload.reasoning),
                    "tool_calls_length": len(assistant_payload.tool_calls),
                    "component_tool_calls_length": len(
                        assistant_payload.component_tool_calls
                    ),
                    **pick_fields(
                        assistant_payload.model_dump(mode="json"),
                        [
                            "tool_calls_duration",
                            "component_tool_calls_duration",
                            "reasoning_duration",
                            "content_duration",
                            "total_duration",
                            "token_stats",
                        ],
                    ),
                    **pick_fields(
                        assistant_message.model_dump(mode="json"), ["updated_at"]
                    ),
                }
                logger.info(
                    "Sending done message",
                    conversation_id=chat_request.conversation_id,
                    **done_payload,
                )
                yield format_sse_message("done", done_payload)
                logger.info(
                    "Stream response generation completed successfully",
                    conversation_id=chat_request.conversation_id,
                )
        except Exception as e:
            logger.error(
                "Error during stream response generation",
                conversation_id=chat_request.conversation_id,
                error=e,
                error_type=type(e).__name__,
            )
            yield format_sse_message(
                "error",
                {
                    "content": str(e),
                    "conversation_id": chat_request.conversation_id,
                },
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
