"""Chat endpoints for message"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.cache import invalidate_conversation_state, invalidate_messages
from app.core.db import get_db
from app.models import ConversationDb, MessageDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import MessageFeedback, MessageFeedbackValue
from app.schemas.response import ApiResponse
from app.utils.auth_deps import get_auth_token_info
from app.utils.date import get_datetime_now

router = APIRouter()


class UpdateMessageFeedbackRequest(BaseModel):
    """更新消息反馈请求"""

    value: MessageFeedbackValue = Field(..., description="反馈值")
    reasons: list[str] | None = Field(
        default=None, description="反馈理由标签（多选）；省略则保留已有值"
    )
    comment: str | None = Field(
        default=None, description="自由文本反馈；省略则保留已有值"
    )


@router.delete("/delete/{message_id}")
async def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[str]:
    """Delete a message by ID"""
    message = db.get(MessageDb, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation = db.get(ConversationDb, message.conversation_id)
    if conversation is None or conversation.user_id != token_info.user_id:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation_id = message.conversation_id
    db.delete(message)
    db.commit()
    await invalidate_messages(conversation_id)
    return ApiResponse.success(data=message_id, msg="消息删除成功")


@router.put("/feedback/{message_id}")
async def update_message_feedback(
    message_id: str,
    request: UpdateMessageFeedbackRequest,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[MessageFeedback]:
    """Update feedback for an assistant message"""
    message = db.get(MessageDb, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation = db.get(ConversationDb, message.conversation_id)
    if conversation is None or conversation.user_id != token_info.user_id:
        raise HTTPException(status_code=404, detail="消息不存在")
    if message.role != "assistant":
        raise HTTPException(status_code=400, detail="仅助手消息支持反馈")

    now = get_datetime_now()
    existing = message.feedback if isinstance(message.feedback, dict) else {}

    if request.value == MessageFeedbackValue.DEFAULT:
        feedback_payload: dict[str, object] = {
            "value": request.value.value,
            "updated_at": now.isoformat(),
            "reasons": [],
            "comment": None,
        }
    else:
        reasons = (
            request.reasons
            if request.reasons is not None
            else existing.get("reasons", [])
        )
        comment = (
            request.comment
            if request.comment is not None
            else existing.get("comment")
        )
        feedback_payload = {
            "value": request.value.value,
            "updated_at": now.isoformat(),
            "reasons": reasons if isinstance(reasons, list) else [],
            "comment": comment if isinstance(comment, str) else None,
        }

    message.feedback = feedback_payload
    message.updated_at = now
    db.add(message)

    conversation.last_message_updated_at = now
    db.add(conversation)

    updated_feedback = MessageFeedback.model_validate(message.feedback)
    conversation_id = message.conversation_id
    db.commit()
    await invalidate_conversation_state(
        conversation_id,
        token_info.user_id,
    )
    return ApiResponse.success(data=updated_feedback, msg="消息反馈更新成功")
