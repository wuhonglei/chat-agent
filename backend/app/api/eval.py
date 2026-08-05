"""评估相关 API：低分复核队列"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.schemas.eval import (
    BadCaseAttribution,
    BadCaseItemResponse,
    BadCaseListResponse,
    BadCaseSource,
    BadCaseStatsResponse,
    BadCaseStatus,
    BadCaseUpdateRequest,
)
from app.schemas.response import ApiResponse
from app.services.eval.bad_case_service import BadCaseService
from app.utils.auth_deps import require_auth

router = APIRouter()


@router.get("/bad-cases")
async def list_bad_cases(
    status: BadCaseStatus | None = None,
    source: BadCaseSource | None = None,
    attribution: BadCaseAttribution | None = None,
    page: int = 1,
    page_size: int = 20,
    _auth: None = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseListResponse]:
    """查询低分复核队列"""
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
    _auth: None = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseStatsResponse]:
    """获取复核队列统计"""
    service = BadCaseService(db)
    stats = service.get_stats()
    return ApiResponse.success(data=stats)


@router.get("/bad-cases/{item_id}")
async def get_bad_case(
    item_id: str,
    _auth: None = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseItemResponse]:
    """获取单条 bad case 详情"""
    service = BadCaseService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bad case 不存在")
    return ApiResponse.success(
        data=BadCaseItemResponse.model_validate(item.model_dump(mode="json"))
    )


@router.put("/bad-cases/{item_id}")
async def update_bad_case(
    item_id: str,
    request: BadCaseUpdateRequest,
    _auth: None = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ApiResponse[BadCaseItemResponse]:
    """更新 bad case（人工归因/处理）"""
    service = BadCaseService(db)
    item = service.update_item(item_id, request)
    if not item:
        raise HTTPException(status_code=404, detail="bad case 不存在")
    return ApiResponse.success(
        data=BadCaseItemResponse.model_validate(item.model_dump(mode="json")),
        msg="更新成功",
    )
