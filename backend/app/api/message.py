"""Chat endpoints for message"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.cache import invalidate_conversation_state, invalidate_messages
from app.core.db import engine, get_db
from app.core.observability import new_trace_id
from app.models import ConversationDb, MessageDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import MessageFeedback, MessageFeedbackValue
from app.schemas.eval import BadCaseSource
from app.schemas.response import ApiResponse
from app.services.eval.bad_case_service import BadCaseService
from app.utils.auth_deps import get_auth_token_info
from app.utils.date import get_datetime_now
from app.utils.logger import logger

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
            request.comment if request.comment is not None else existing.get("comment")
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

    # 用户点踩时自动入队 bad case（fire-and-forget）
    if request.value == MessageFeedbackValue.DISLIKE:
        asyncio.create_task(
            _enqueue_thumb_down_bad_case(
                message_id=message_id,
                conversation_id=message.conversation_id,
                user_id=token_info.user_id,
                feedback_reasons=request.reasons or [],
                feedback_comment=request.comment,
            )
        )

    # 用户取消点踩时，dismiss 队列中 pending 的 bad case
    if (
        request.value == MessageFeedbackValue.DEFAULT
        and existing.get("value") == MessageFeedbackValue.DISLIKE.value
    ):
        asyncio.create_task(_dismiss_thumb_down_bad_case(message_id=message_id))

    return ApiResponse.success(data=updated_feedback, msg="消息反馈更新成功")


async def _enqueue_thumb_down_bad_case(
    *,
    message_id: str,
    conversation_id: str,
    user_id: str,
    feedback_reasons: list[str],
    feedback_comment: str | None,
) -> None:
    """Fire-and-forget: 用户点踩时将样本加入 bad case 复核队列。"""
    try:
        with Session(engine) as db:
            # 获取用户问题和模型回答
            msg = db.get(MessageDb, message_id)
            query = ""
            answer = ""
            if msg:
                answer = _extract_text_from_content_blocks(msg.content_blocks or [])
                # 获取关联的用户消息
                if msg.reply_to:
                    user_msg = db.get(MessageDb, msg.reply_to)
                    if user_msg:
                        query = _extract_text_from_content_blocks(
                            user_msg.content_blocks or []
                        )

            service = BadCaseService(db)
            service.enqueue(
                source=BadCaseSource.THUMB_DOWN,
                message_id=message_id,
                conversation_id=conversation_id,
                user_id=user_id,
                query=query,
                answer=answer,
                feedback_reasons=feedback_reasons,
                feedback_comment=feedback_comment,
                # 与 chat-turn 埋点一致：用 assistant message_id 派生确定性 trace_id
                trace_id=new_trace_id(message_id),
            )
            db.commit()
    except Exception as exc:
        logger.warning(
            "Failed to enqueue bad case from thumb down",
            error=exc,
            error_type=type(exc).__name__,
        )


async def _dismiss_thumb_down_bad_case(*, message_id: str) -> None:
    """Fire-and-forget: 用户取消点踩时，dismiss 队列中 pending 的 bad case。"""
    try:
        with Session(engine) as db:
            service = BadCaseService(db)
            service.dismiss_by_message(message_id)
            db.commit()
    except Exception as exc:
        logger.warning(
            "Failed to dismiss bad case on thumb-down cancel",
            error=exc,
            error_type=type(exc).__name__,
        )


def _extract_text_from_content_blocks(blocks: list[dict[str, Any]]) -> str:
    """从 content_blocks 中提取纯文本。"""
    parts: list[str] = []
    for block in blocks:
        text = block.get("content") or block.get("text")
        if block.get("type") == "text" and text:
            parts.append(str(text))
    return " ".join(parts)[:500]
