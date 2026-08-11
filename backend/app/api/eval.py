"""评估相关 API：低分复核队列"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.schemas.auth import AuthTokenPayload
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
from app.utils.auth_deps import require_admin

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
