"""Chat endpoints for message"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.db import get_db
from app.models import MessageDb
from app.schemas.chat import MessageFeedback, MessageFeedbackValue
from app.schemas.response import ApiResponse
from app.utils.auth_deps import require_auth
from app.utils.date import get_datetime_now

router = APIRouter()


class UpdateMessageFeedbackRequest(BaseModel):
    """更新消息反馈请求"""

    value: MessageFeedbackValue = Field(..., description="反馈值")


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


@router.put("/feedback/{message_id}")
async def update_message_feedback(
    message_id: str,
    request: UpdateMessageFeedbackRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[MessageFeedback]:
    """Update feedback for an assistant message"""
    message = db.get(MessageDb, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    if message.role != "assistant":
        raise HTTPException(status_code=400, detail="仅助手消息支持反馈")

    now = get_datetime_now()
    message.feedback = {
        "value": request.value.value,
        "updated_at": now.isoformat(),
    }
    message.updated_at = now
    db.add(message)

    updated_feedback = MessageFeedback.model_validate(message.feedback)
    return ApiResponse.success(data=updated_feedback, msg="消息反馈更新成功")
