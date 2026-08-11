"""评估相关 API：低分复核队列 + 评估运行日志"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.core.observability import init_langfuse
from app.schemas.auth import AuthTokenPayload
from app.schemas.eval import (
    BadCaseAttribution,
    BadCaseItemResponse,
    BadCaseListResponse,
    BadCaseSource,
    BadCaseStatsResponse,
    BadCaseStatus,
    BadCaseUpdateRequest,
    EvalRunLogListResponse,
    EvalRunLogResponse,
    EvalRunStatus,
    EvalRunTriggerRequest,
    EvalRunType,
)
from app.schemas.response import ApiResponse
from app.services.eval.bad_case_service import BadCaseService
from app.services.eval.batch_eval_service import BatchEvalService
from app.services.eval.eval_run_log_service import EvalRunLogService
from app.services.eval.judge_llm import judge_llm_caller
from app.utils.auth_deps import require_admin
from app.utils.logger import logger

router = APIRouter()


@router.get("/bad-cases")
async def list_bad_cases(
    status: BadCaseStatus | None = None,
    source: BadCaseSource | None = None,
    attribution: BadCaseAttribution | None = None,
    page: int = 1,
    page_size: int = 20,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseListResponse]:
    """查询低分复核队列（仅 admin）"""
    service = BadCaseService(db)
    result = service.list_items(
        status=status,
        source=source,
        attribution=attribution,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data=result)


@router.get("/bad-cases/stats")
async def get_bad_case_stats(
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseStatsResponse]:
    """获取复核队列统计（仅 admin）"""
    service = BadCaseService(db)
    stats = service.get_stats()
    return ApiResponse.success(data=stats)


@router.get("/bad-cases/{item_id}")
async def get_bad_case(
    item_id: str,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseItemResponse]:
    """获取单条 bad case 详情（仅 admin）"""
    service = BadCaseService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bad case 不存在")
    return ApiResponse.success(data=service.to_response(item))


@router.put("/bad-cases/{item_id}")
async def update_bad_case(
    item_id: str,
    request: BadCaseUpdateRequest,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseItemResponse]:
    """更新 bad case（人工归因/处理，仅 admin）"""
    service = BadCaseService(db)
    item = service.update_item(item_id, request)
    if not item:
        raise HTTPException(status_code=404, detail="bad case 不存在")
    return ApiResponse.success(
        data=service.to_response(item),
        msg="更新成功",
    )


@router.post("/bad-cases/{item_id}/add-to-dataset")
async def add_bad_case_to_dataset(
    item_id: str,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseItemResponse]:
    """将 bad case 推送到固定 Langfuse dataset（仅 admin）"""
    service = BadCaseService(db)
    try:
        item = service.add_to_dataset(item_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="bad case 不存在") from None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"推送 Langfuse dataset 失败: {e}",
        ) from e
    return ApiResponse.success(
        data=service.to_response(item),
        msg="已添加到 Langfuse dataset",
    )


# ── 评估运行日志 ──


@router.get("/run-logs")
async def list_run_logs(
    status: EvalRunStatus | None = None,
    run_type: EvalRunType | None = None,
    page: int = 1,
    page_size: int = 20,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[EvalRunLogListResponse]:
    """分页查询评估运行日志（仅 admin）"""
    service = EvalRunLogService(db)
    result = service.list_run_logs(
        status=status,
        run_type=run_type,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data=result)


@router.post("/run-logs/trigger")
async def trigger_batch_eval(
    request: EvalRunTriggerRequest = EvalRunTriggerRequest(),
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[EvalRunLogResponse]:
    """手动触发批量评估（仅 admin）。立即返回 run id，后台异步执行。"""
    log_service = EvalRunLogService(db)
    if log_service.has_running():
        raise HTTPException(status_code=409, detail="已有评估在运行，请稍后再试")

    batch_service = BatchEvalService(llm_caller=judge_llm_caller)
    run_log = batch_service.create_run_log(run_type=EvalRunType.MANUAL.value)
    asyncio.create_task(
        _run_batch_eval_background(run_id=run_log.id, hours=request.hours),
        name=f"batch-eval-{run_log.id}",
    )
    return ApiResponse.success(
        data=EvalRunLogService.to_response(run_log),
        msg="批量评估已开始",
    )


@router.get("/run-logs/{run_id}")
async def get_run_log(
    run_id: str,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[EvalRunLogResponse]:
    """获取单条评估运行日志（仅 admin，供轮询）"""
    service = EvalRunLogService(db)
    item = service.get_run_log(run_id)
    if not item:
        raise HTTPException(status_code=404, detail="评估运行日志不存在")
    return ApiResponse.success(data=service.to_response(item))


@router.delete("/run-logs/{run_id}")
async def delete_run_log(
    run_id: str,
    _auth: AuthTokenPayload = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    """删除单条评估运行日志（仅 admin）。运行中不可删。"""
    service = EvalRunLogService(db)
    try:
        deleted = service.delete_run_log(run_id)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail="评估运行日志不存在")
    return ApiResponse.success(msg="删除成功")


async def _run_batch_eval_background(*, run_id: str, hours: int | None) -> None:
    """Fire-and-forget: 后台执行批量评估。"""
    try:
        init_langfuse()
        service = BatchEvalService(llm_caller=judge_llm_caller)
        await service.execute_run(run_id, hours=hours, dry_run=False)
    except Exception as exc:
        logger.error(
            "Background batch eval failed",
            run_id=run_id,
            error=exc,
            error_type=type(exc).__name__,
            exc_info=True,
        )
