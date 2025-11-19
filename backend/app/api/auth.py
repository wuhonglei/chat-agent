"""
用户认证
"""

from fastapi import APIRouter, Depends, Response
from loguru import logger
from sqlmodel import Session
from app.core.db import get_db
from app.models.auth import SendSmsRequest, SendSmsResponse, VerifySmsRequestFromFrontend
from app.models.auth import SigninRequest, SignupRequest
from app.models.db import UserDb
from app.models.response import ApiResponse
from app.services.cloudbase_service import CloudbaseService
from app.services.user_service import UserService
from app.utils.auth_helper import create_server_tokens

router = APIRouter()


@router.post("/send_sms")
async def send_sms(send_sms_request: SendSmsRequest) -> ApiResponse[SendSmsResponse]:
    """发送短信验证码"""
    data = await CloudbaseService.send_sms(send_sms_request)
    return ApiResponse.success(data=data)


@router.post("/verify_sms")
async def verify_sms(
    verify_sms_request: VerifySmsRequestFromFrontend,
    response: Response,
    db: Session = Depends(get_db)
) -> ApiResponse[UserDb]:
    """验证短信验证码"""
    data = await CloudbaseService.verify_sms(verify_sms_request)
    verification_token = data.verification_token
    user_service = UserService(db)

    # 如果是新用户，则先注册，否则直接登录
    if verify_sms_request.is_user:
        phone_number = verify_sms_request.phone_number
        token_info = await CloudbaseService.signup(SignupRequest(verification_token=verification_token, phone_number=phone_number))
        user = user_service.create_user_from_cloudbase(
            token_info, phone_number)
    else:
        # 如果是老用户，则直接登录
        token_info = await CloudbaseService.signin(SigninRequest(verification_token=verification_token))
        user = user_service.update_user_last_login_from_cloudbase(
            token_info.sub)

    # 设置自定义响应头
    response.headers["x-secret-token-info"] = create_server_tokens(token_info)

    return ApiResponse.success(data=user)
