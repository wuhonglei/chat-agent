"""Retrieval system endpoints"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from app.models.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_manager import RetrievalManager
from app.models.app_state import AppState

router = APIRouter()


@router.post("/search", response_model=RetrievalResponse)
async def search(request: Request, retrieval_request: RetrievalRequest) -> RetrievalResponse:
    """Search across multiple retrieval sources"""
    try:
        # Get vector manager
        state = cast(AppState, request.app.state)
        vector_manager = state.vector_manager

        # Initialize retrieval manager
        retrieval_manager = RetrievalManager(vector_manager)

        # Perform search
        response = await retrieval_manager.retrieve(retrieval_request)

        return response

    except Exception as e:
        logger.error(f"Retrieval search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(request: Request):
    """Check health of all retrieval sources"""
    try:
        # Get vector manager
        state = cast(AppState, request.app.state)
        vector_manager = state.vector_manager

        # Initialize retrieval manager
        retrieval_manager = RetrievalManager(vector_manager)

        # Check health
        health_status = await retrieval_manager.health_check()

        return {
            "status": "healthy" if all(health_status.values()) else "degraded",
            "sources": health_status,
            "available_sources": retrieval_manager.get_available_sources(),
        }

    except Exception as e:
        logger.error(f"Retrieval health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_sources(request: Request):
    """Get available retrieval sources"""
    try:
        # Get vector manager
        state = cast(AppState, request.app.state)
        vector_manager = state.vector_manager

        # Initialize retrieval manager
        retrieval_manager = RetrievalManager(vector_manager)

        return {
            "available_sources": retrieval_manager.get_available_sources(),
        }

    except Exception as e:
        logger.error(f"Failed to get retrieval sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_retrievers(request: Request):
    """Reload all retrievers (for configuration changes)"""
    try:
        # Get vector manager
        state = cast(AppState, request.app.state)
        vector_manager = state.vector_manager

        # Initialize retrieval manager
        retrieval_manager = RetrievalManager(vector_manager)

        # Reload retrievers
        retrieval_manager.reload_retrievers()

        return {"message": "Retrievers reloaded successfully"}

    except Exception as e:
        logger.error(f"Failed to reload retrievers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
