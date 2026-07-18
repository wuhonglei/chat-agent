"""腾讯云短信服务

发送短信使用腾讯云短信 SDK；验证码校验与短信登录由本系统完成。
"""

import asyncio
import random
import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.models import UserDb
from app.schemas.auth import SendSmsRequest, SendSmsResponse, SmsLoginRequest
from app.services.auth.sms_verification_store import SmsVerificationStore
from app.services.user import UserDbService
from app.utils.logger import logger
from app.utils.sms import format_phone_e164, send_sms_sync

_store = SmsVerificationStore()
VERIFICATION_TTL = SmsVerificationStore.TTL_SECONDS


class SmsService:
    """短信服务类（腾讯云短信 + 自建验证）"""

    @staticmethod
    async def send_sms(
        send_sms_request: SendSmsRequest, db: Session
    ) -> SendSmsResponse:
        """发送短信验证码（腾讯云短信 SDK + 6 位验证码 + Redis 缓存）

        Args:
            send_sms_request: 包含 phone_number
            db: 数据库会话，用于查询 is_user

        Returns:
            verification_id, expires_in, is_user

        Raises:
            HTTPException: 当请求失败时
        """
        phone = send_sms_request.phone_number.strip()
        code = "".join(random.choices("0123456789", k=6))
        verification_id = str(uuid.uuid4())
        try:
            await _store.save(verification_id, code=code, phone=phone)
        except Exception as e:
            logger.error("验证码写入 Redis 失败", error=e, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="验证码服务暂不可用",
            ) from e

        phone_e164 = format_phone_e164(phone)
        try:
            await asyncio.to_thread(send_sms_sync, phone_e164, code, settings.sms)
        except Exception as e:  # noqa: BLE001
            try:
                await _store.delete(verification_id)
            except Exception as delete_error:
                logger.error(
                    "验证码回滚 Redis 失败",
                    error=delete_error,
                    exc_info=True,
                )
            if (
                type(e).__name__ == "TencentCloudSDKException"
                and "PhoneNumberThirtySecondLimit" in str(e)
            ):
                raise HTTPException(
                    status_code=429,
                    detail="发送过于频繁，请 30 秒后再试",
                ) from e
            logger.error("腾讯云短信发送失败", error=e)
            raise HTTPException(
                status_code=500,
                detail="发送短信验证码失败",
            ) from e
        return SendSmsResponse(
            verification_id=verification_id,
            expires_in=VERIFICATION_TTL,
            phone_number=phone,
        )

    @staticmethod
    async def sms_login(sms_login_request: SmsLoginRequest, db: Session) -> UserDb:
        """短信登录（自建验证 + 本系统用户，不再调用 Cloudbase verify/signin/signup）

        Args:
            sms_login_request: verification_id, verification_code, 前端会带 phone_number
            db: 数据库会话

        Returns:
            UserDb 供 auth 直接写 JWT
        """
        vid = sms_login_request.verification_id
        try:
            entry = await _store.get(vid)
        except Exception as e:
            logger.error("验证码读取 Redis 失败", error=e, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="验证码服务暂不可用",
            ) from e

        if entry is None:
            raise HTTPException(status_code=400, detail="验证码已过期或无效")
        if entry.code != sms_login_request.verification_code:
            raise HTTPException(status_code=400, detail="验证码错误")
        if entry.phone != sms_login_request.phone_number:
            raise HTTPException(status_code=400, detail="手机号不匹配")

        await _store.delete(vid)
        user = UserDbService(db).get_or_create_user_by_phone(entry.phone)
        return user
