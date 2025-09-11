"""Health check endpoints"""

from fastapi import APIRouter, Response

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    # TODO: Check if all services are ready
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return {"status": "alive"}
