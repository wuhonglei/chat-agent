"""Cloudbase 服务

用于调用 Cloudbase 认证相关的 API
"""
import httpx
from fastapi import HTTPException
from loguru import logger

from app.core.config import settings
from app.models.auth import SendSmsRequest, SendSmsResponse, SigninRequest, SigninResponse, SignupRequest, SignupResponse, RefreshTokenRequest, RefreshTokenResponse, VerifySmsRequest, VerifySmsResponse


class CloudbaseService:
    """Cloudbase 服务类"""
    VERIFY_SSL = not settings.DEBUG  # 如果DEBUG为True，则不验证SSL证书
    BASE_URL = f"https://{settings.CLOUDBASE_ENV_ID}.api.tcloudbasegateway.com"

    @staticmethod
    async def send_sms(send_sms_request: SendSmsRequest) -> SendSmsResponse:
        """发送短信验证码

        Args:
            phone_number: 手机号码

        Returns:
            verification_id: 验证码 ID，用于后续验证

        Raises:
            HTTPException: 当请求失败时
        """
        url = f"{CloudbaseService.BASE_URL}/auth/v1/verification"

        payload = send_sms_request.model_dump(exclude_none=True)

        async with httpx.AsyncClient(verify=CloudbaseService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return SendSmsResponse(**data)
                else:
                    logger.error(
                        f"Cloudbase 发送短信失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"发送短信验证码失败: {response.text}"
                    )
            except httpx.RequestError as e:
                logger.error(f"Cloudbase 发送短信请求失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="认证服务暂时不可用"
                )

    @staticmethod
    async def verify_sms(verify_sms_request: VerifySmsRequest) -> VerifySmsResponse:
        """验证短信验证码

        Args:
            verification_id: 验证码 ID
            verification_code: 验证码

        Returns:
            包含 verification_token 的字典

        Raises:
            HTTPException: 当验证失败时
        """
        url = f"{CloudbaseService.BASE_URL}/auth/v1/verification/verify"

        payload = verify_sms_request.model_dump(exclude_none=True)

        async with httpx.AsyncClient(verify=CloudbaseService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return VerifySmsResponse(**data)
                else:
                    logger.error(
                        f"Cloudbase 验证短信失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail="验证短信验证码失败"
                    )
            except httpx.RequestError as e:
                logger.error(f"Cloudbase 验证短信请求失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="认证服务暂时不可用"
                )

    @staticmethod
    async def signin(signin_request: SigninRequest) -> SigninResponse:
        """使用验证码登录

        Args:
            signin_request: 登录请求

        Returns:
            Cloudbase 返回的 token 信息

        Raises:
            HTTPException: 当登录失败时
        """
        url = f"{CloudbaseService.BASE_URL}/auth/v1/signin"

        payload = signin_request.model_dump(exclude_none=True)

        async with httpx.AsyncClient(verify=CloudbaseService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return SigninResponse(**data)
                else:
                    logger.error(
                        f"Cloudbase 登录失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"登录失败: {response.text}"
                    )
            except httpx.RequestError as e:
                logger.error(f"Cloudbase 登录请求失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="认证服务暂时不可用"
                )

    @staticmethod
    async def signup(signup_request: SignupRequest) -> SignupResponse:
        """注册新用户

        Args:
            signup_request: 注册请求

        Returns:
            Cloudbase 返回的 token 信息

        Raises:
            HTTPException: 当注册失败时
        """
        url = f"{CloudbaseService.BASE_URL}/auth/v1/signup"

        payload = signup_request.model_dump(exclude_none=True)

        async with httpx.AsyncClient(verify=CloudbaseService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return SignupResponse(**data)
                else:
                    logger.error(
                        f"Cloudbase 注册失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"注册失败: {response.text}"
                    )
            except httpx.RequestError as e:
                logger.error(f"Cloudbase 注册请求失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="认证服务暂时不可用"
                )

    @staticmethod
    async def refresh_token(refresh_token_request: RefreshTokenRequest) -> RefreshTokenResponse:
        """刷新 Cloudbase token

        Args:
            cloudbase_refresh_token: Cloudbase 的 refresh_token

        Returns:
            Cloudbase 返回的新 token 信息

        Raises:
            HTTPException: 当刷新失败时
        """
        url = f"{CloudbaseService.BASE_URL}/auth/v1/token"

        payload = refresh_token_request.model_dump(exclude_none=True)

        async with httpx.AsyncClient(verify=CloudbaseService.VERIFY_SSL) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return RefreshTokenResponse(**data)
                else:
                    logger.error(
                        f"Cloudbase token 刷新失败: {response.status_code}, "
                        f"{response.text}"
                    )
                    raise HTTPException(
                        status_code=401,
                        detail="Token 刷新失败，请重新登录"
                    )
            except httpx.RequestError as e:
                logger.error(f"Cloudbase token 刷新请求失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="认证服务暂时不可用"
                )
