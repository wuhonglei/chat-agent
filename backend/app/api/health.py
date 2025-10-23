"""Health check endpoints"""

from fastapi import APIRouter, HTTPException, Request
from typing import cast
from app.models.app_state import AppState
from loguru import logger


router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}


@router.get("/mcp")
async def mcp_health_check(request: Request):
    """MCP health check"""
    state = cast(AppState, request.app.state)
    try:
        return await state.mcp_manager.health_check()
    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp_config")
async def mcp_config(request: Request):
    """Get MCP config for FE"""
    state = cast(AppState, request.app.state)
    try:
        return await state.mcp_manager.get_mcp_config_for_fe()
    except Exception as e:
        logger.error(f"Get MCP config for FE failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
