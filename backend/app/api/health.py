"""Health check endpoints: live / ready / deep."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.health_probes import run_deep_probes, run_ready_probes
from app.schemas.response import ApiResponse

router = APIRouter()


def _json_response(
    *,
    status_code: int,
    data: dict[str, Any],
    msg: str,
    code: int = 0,
) -> JSONResponse:
    body = ApiResponse(code=code, msg=msg, data=data).model_dump()
    return JSONResponse(status_code=status_code, content=body)


@router.get("/live")
async def health_live() -> ApiResponse[dict[str, str]]:
    """Liveness: process can respond."""
    return ApiResponse.success(
        data={"status": "alive"},
        msg="存活检查成功",
    )


@router.get("/ready", response_model=None)
async def health_ready() -> ApiResponse[dict[str, Any]] | JSONResponse:
    """Readiness: Postgres + Redis must be up."""
    result = await run_ready_probes()
    if not result["ready"]:
        return _json_response(
            status_code=503,
            data=result,
            msg="服务未就绪",
            code=1,
        )
    return ApiResponse.success(data=result, msg="就绪检查成功")


@router.get("", response_model=None)
async def health_check() -> ApiResponse[dict[str, Any]] | JSONResponse:
    """Deep health: hard deps + pool stats + LLM reachability."""
    result = await run_deep_probes()
    if not result["ready"]:
        return _json_response(
            status_code=503,
            data=result,
            msg="健康检查失败",
            code=1,
        )
    msg = "健康检查成功" if result["status"] == "healthy" else "服务降级"
    return ApiResponse.success(data=result, msg=msg)
