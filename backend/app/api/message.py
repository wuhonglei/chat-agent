"""Chat endpoints for message"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from sqlmodel import Session
from fastapi import Depends
from app.core.db import get_db
from app.models.response import ApiResponse
from app.models.db import MessageDb
from app.utils.auth_deps import require_auth

router = APIRouter()


@router.delete("/delete/{message_id}")
async def delete_message(message_id: str, db: Session = Depends(get_db), _auth: None = Depends(require_auth)):
    """Delete a message by ID"""
    try:
        message = db.get(MessageDb, message_id)
        if not message:
            return ApiResponse.error(code=404, msg="消息不存在", data=None)
        db.delete(message)
        db.commit()
        return ApiResponse.success(data=message_id, msg="消息删除成功")
    except Exception as exc:
        logger.error(f"Failed to delete message: {exc}")
        raise HTTPException(status_code=500, detail="消息删除失败") from exc
