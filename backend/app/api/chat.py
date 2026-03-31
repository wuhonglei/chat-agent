"""Chat endpoints for Q&A"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_mcp_manager
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import ChatRequest
from app.services.chat import ChatService
from app.services.message import MessageDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.logger import logger

router = APIRouter()


@router.post("/stream")
async def chat_stream(
    chat_request: ChatRequest,
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> StreamingResponse:
    """Stream chat response, 按需保存用户与助手消息。user_id 用于 Mem0 记忆与 user_context 注入。"""
    logger.info(
        "Chat stream request received",
        chat_request=chat_request.model_dump(exclude_none=True),
    )

    user_metadata = chat_request.model_dump(
        exclude_none=True, exclude={"content_blocks"}
    )
    with MessageDbService() as message_service:
        messages_result = message_service.create_chat_messages(
            conversation_id=chat_request.conversation_id,
            content_blocks=chat_request.content_blocks,
            user_metadata=user_metadata,
            removed_message_ids=chat_request.removed_message_ids,
        )
    logger.info(
        "Messages created",
        conversation_id=chat_request.conversation_id,
        user_message_id=messages_result.user_message_id,
        assistant_message_id=messages_result.assistant_message_id,
    )

    chat_service = ChatService(
        think_mode=chat_request.think_mode,
        mcp_manager=mcp_manager,
        chat_context_config=settings.chat_context,
    )
    return StreamingResponse(
        chat_service.stream_response(
            chat_request,
            messages_result.user_message_id,
            messages_result.assistant_message_id,
            user_id=auth_info.user_id,
        ),
        media_type="text/event-stream",
    )
