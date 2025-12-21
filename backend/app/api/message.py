"""Chat endpoints for message"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.models.db import MessageDb
from app.models.response import ApiResponse
from app.utils.auth_deps import require_auth

router = APIRouter()


@router.delete("/delete/{message_id}")
async def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """Delete a message by ID"""
    message = db.get(MessageDb, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    db.delete(message)
    # 事务由 get_db() 自动提交
    return ApiResponse.success(data=message_id, msg="消息删除成功")
