"""Chat endpoints for Q&A"""

import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.chat import ChatRequest, ChatResponse, ChatSession
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: Request, chat_request: ChatRequest) -> ChatResponse:
    """Process chat message and return response"""
    try:
        # Get or create session ID
        session_id = chat_request.session_id or str(uuid.uuid4())

        # Get vector store
        vector_store = request.app.state.vector_store

        # Initialize chat service
        chat_service = ChatService(vector_store)

        # Process message
        response = await chat_service.process_message(
            message=chat_request.message,
            session_id=session_id,
            history=chat_request.history,
            use_knowledge_base=chat_request.use_knowledge_base,
        )

        return response

    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Stream chat response"""
    try:
        # Get or create session ID
        session_id = chat_request.session_id or str(uuid.uuid4())

        # Get vector store
        vector_store = request.app.state.vector_store

        # Initialize chat service
        chat_service = ChatService(vector_store)

        # Stream response
        async def generate() -> AsyncGenerator[str, None]:
            async for chunk in chat_service.stream_message(
                message=chat_request.message,
                session_id=session_id,
                history=chat_request.history,
                use_knowledge_base=chat_request.use_knowledge_base,
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
        raise HTTPException(status_code=501, detail="Session management not implemented yet")

    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete chat session"""
    try:
        # TODO: Implement session deletion
        raise HTTPException(status_code=501, detail="Session management not implemented yet")

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
