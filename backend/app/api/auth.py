"""
用户认证
"""

from fastapi import APIRouter
from loguru import logger
from app.models.auth import SendSmsRequest, SendSmsResponse, VerifySmsRequest, VerifySmsRequestFromFrontend, VerifySmsResponse
from app.models.auth import SigninRequest, SigninResponse, SignupRequest, SignupResponse, RefreshTokenRequest, RefreshTokenResponse
from app.models.response import ApiResponse
from app.services.cloudbase_service import CloudbaseService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/send_sms")
async def send_sms(send_sms_request: SendSmsRequest) -> ApiResponse[SendSmsResponse]:
    """发送短信验证码"""
    data = await CloudbaseService.send_sms(send_sms_request)
    return ApiResponse.success(data=data)


@router.post("/verify_sms")
async def verify_sms(verify_sms_request: VerifySmsRequestFromFrontend) -> ApiResponse[VerifySmsResponse]:
    """验证短信验证码"""
    data = await CloudbaseService.verify_sms(verify_sms_request)
    if verify_sms_request.is_user:
        data = await CloudbaseService.signup(verify_sms_request)
        with UserService() as user_service:
            user_service.create_user(data)
    else:
        data = await CloudbaseService.signin(verify_sms_request)
    return ApiResponse.success(data=data)
