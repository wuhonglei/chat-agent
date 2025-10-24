"""Chat endpoints for Q&A"""

import uuid
from collections.abc import AsyncGenerator
from typing import cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.chat import ChatRequest, ChatSession
from app.services.chat_service import ChatService
from app.models.app_state import AppState

router = APIRouter()


@router.post("/stream")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Stream chat response"""
    try:
        # Get or create session ID
        session_id = chat_request.session_id or str(uuid.uuid4())
        state = cast(AppState, request.app.state)

        # Initialize chat service
        chat_service = ChatService(mcp_manager=state.mcp_manager)

        # Stream response
        async def generate() -> AsyncGenerator[str, None]:
            async for chunk in chat_service.stream_message(
                session_id=session_id,
                chat_request=chat_request
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.error(f"Chat streaming failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str) -> ChatSession:
    """Get chat session history"""
    try:
        # TODO: Implement session storage and retrieval
        raise HTTPException(
            status_code=501, detail="Session management not implemented yet")

    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete chat session"""
    try:
        # TODO: Implement session deletion
        raise HTTPException(
            status_code=501, detail="Session management not implemented yet")

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
