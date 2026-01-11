"""Chat endpoints for Q&A"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.mcp.mcp_client import MCPClientManager
from app.schemas.chat import ChatRequest, MessageStatus
from app.models import MessageDb
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.utils.auth_deps import require_auth
from app.utils.common import include_fields
from app.utils.logger import logger
from app.utils.model import format_sse_message
from app.utils.network import get_public_client_ip
from app.utils.time import get_current_time, get_time_duration

router = APIRouter()


def get_mcp_manager(request: Request) -> MCPClientManager:
    """获取 MCP Manager 依赖注入函数"""
    return request.app.state.mcp_manager


@router.post("/stream")
async def chat_stream(
    chat_request: ChatRequest,
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
    _auth: None = Depends(require_auth),
    client_ip: str | None = Depends(get_public_client_ip),
):
    """Stream chat response, 按需保存用户与助手消息"""
    logger.info(
        "Chat stream request received",
        chat_request=chat_request.model_dump(exclude_none=True),
    )

    user_metadata = chat_request.model_dump(
        exclude_none=True, exclude=['content']
    )

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
        with MessageService() as message_service:
            conversation = message_service.get_conversation(
                chat_request.conversation_id)
            user_message = message_service.session.get(
                MessageDb, user_message_id)
            assistant_message = message_service.session.get(
                MessageDb, assistant_message_id)

            # 发送初始确认消息
            yield format_sse_message('ack', user_message)
            yield format_sse_message('ack', assistant_message)
            yield format_sse_message('refresh_conversation', conversation)

            chat_service = ChatService(
                think_mode=chat_request.think_mode,
                mcp_manager=mcp_manager)

            # 如果需要重新生成标题
            if chat_request.regenerate_title:
                title = await chat_service.generate_title(chat_request.content)
                yield format_sse_message('title', {
                    'id': chat_request.conversation_id,
                    'title': title,
                    'token_stats': chat_service.title_generation_agent.token_stats.model_dump(mode="json"),
                })

            # 流式生成响应
            start_time = get_current_time()
            history = message_service.get_flatten_messages_by_ids(
                chat_request.history_ids
            )
            async for chunk in chat_service.stream_message(
                chat_request=chat_request,
                history=history,
                client_ip=client_ip
            ):
                yield chunk

            # 更新助手消息
            chat_service.total_duration = get_time_duration(start_time)
            assistant_payload = chat_service.get_collected_response()
            assistant_message = message_service.update_assistant_message(
                conversation,
                assistant_message,
                assistant_payload=assistant_payload,
                status=MessageStatus.DONE,
            )

            # 发送完成消息
            yield format_sse_message('done', {
                'content_length': len(assistant_payload.content),
                'reasoning_length': len(assistant_payload.reasoning),
                'tool_calls_length': len(assistant_payload.tool_calls),
                'component_tool_calls_length': len(assistant_payload.component_tool_calls),
                **include_fields(assistant_payload, ['tool_calls_duration', 'component_tool_calls_duration', 'reasoning_duration', 'content_duration', 'total_duration', 'token_stats']),
                **include_fields(assistant_message, ['updated_at']),
            })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
