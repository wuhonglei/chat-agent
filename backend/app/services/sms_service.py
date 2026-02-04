"""腾讯云短信服务

发送短信使用腾讯云短信 SDK；验证码校验与短信登录由本系统完成。
"""

import asyncio
import random
import time
import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.schemas.auth import (
    SendSmsRequest,
    SendSmsResponse,
    SigninRequest,
    SigninResponse,
    SignupRequest,
    SignupResponse,
    SmsLoginRequest,
    SmsLoginResponse,
    SmsVerificationEntry,
)
from app.services.user_service import UserService
from app.utils.logger import logger
from app.utils.sms import format_phone_e164, send_sms_sync

# 验证码缓存：key=verification_id, value={"code", "phone", "expires_at"}
_verification_cache: dict[str, SmsVerificationEntry] = {}
VERIFICATION_TTL = 300  # 秒


class SmsService:
    """短信服务类（腾讯云短信 + 自建验证）"""

    VERIFY_SSL = not settings.app.debug  # 保留供 signin/signup 使用
    BASE_URL = f"https://{settings.cloudbase.env_id}.api.tcloudbasegateway.com"

    @staticmethod
    async def send_sms(
        send_sms_request: SendSmsRequest, db: Session
    ) -> SendSmsResponse:
        """发送短信验证码（腾讯云短信 SDK + 6 位验证码 + 进程内缓存）

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
        now = time.time()
        _verification_cache[verification_id] = SmsVerificationEntry(
            code=code,
            phone=phone,
            expires_at=now + VERIFICATION_TTL,
        )
        phone_e164 = format_phone_e164(phone)
        try:
            await asyncio.to_thread(send_sms_sync, phone_e164, code, settings.sms)
        except Exception as e:  # noqa: BLE001
            if verification_id in _verification_cache:
                del _verification_cache[verification_id]
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
        is_user = UserService(db).get_user_by_phone(phone) is not None
        return SendSmsResponse(
            verification_id=verification_id,
            expires_in=VERIFICATION_TTL,
            is_user=is_user,
        )

    @staticmethod
    async def sms_login(
        sms_login_request: SmsLoginRequest, db: Session
    ) -> SmsLoginResponse:
        """短信登录（自建验证 + 本系统用户，不再调用 Cloudbase verify/signin/signup）

        Args:
            sms_login_request: verification_id, verification_code, 前端会带 phone_number
            db: 数据库会话

        Returns:
            SmsLoginResponse(user=user, ...) 供 auth 直接写 JWT
        """
        vid = sms_login_request.verification_id
        if vid not in _verification_cache:
            raise HTTPException(status_code=400, detail="验证码已过期或无效")
        entry = _verification_cache[vid]
        if time.time() > entry.expires_at:
            del _verification_cache[vid]
            raise HTTPException(status_code=400, detail="验证码已过期")
        if entry.code != sms_login_request.verification_code:
            raise HTTPException(status_code=400, detail="验证码错误")
        phone = entry.phone
        request_phone = getattr(sms_login_request, "phone_number", None)
        if request_phone is not None and request_phone.strip() != phone:
            raise HTTPException(status_code=400, detail="手机号与验证码不匹配")
        del _verification_cache[vid]
        user = UserService(db).get_or_create_user_by_phone(phone)
        return SmsLoginResponse(
            user=user,
            verification_token="",
            expires_in=0,
        )

    @staticmethod
    async def signin(signin_request: SigninRequest) -> SigninResponse:
        """使用验证码登录（Cloudbase，短信登录流程已改为自建，此方法保留兼容）"""
        import httpx

        url = f"{SmsService.BASE_URL}/auth/v1/signin"
        payload = signin_request.model_dump(exclude_none=True)
        async with httpx.AsyncClient(verify=SmsService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return SigninResponse(**data)
                logger.error(
                    "Cloudbase 登录失败",
                    status_code=response.status_code,
                    detail=response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"登录失败: {response.text}",
                )
            except httpx.RequestError as e:
                logger.error("Cloudbase 登录请求失败", error=e)
                raise HTTPException(status_code=500, detail="认证服务暂时不可用")

    @staticmethod
    async def signup(signup_request: SignupRequest) -> SignupResponse:
        """注册新用户（Cloudbase，短信登录流程已改为自建，此方法保留兼容）"""
        import httpx

        url = f"{SmsService.BASE_URL}/auth/v1/signup"
        payload = signup_request.model_dump(exclude_none=True)
        async with httpx.AsyncClient(verify=SmsService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return SignupResponse(**data)
                logger.error(
                    "Cloudbase 注册失败",
                    status_code=response.status_code,
                    detail=response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"注册失败: {response.text}",
                )
            except httpx.RequestError as e:
                logger.error("Cloudbase 注册请求失败", error=e)
                raise HTTPException(status_code=500, detail="认证服务暂时不可用")
