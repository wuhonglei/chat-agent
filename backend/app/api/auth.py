"""
用户认证
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session

from app.core.db import get_db
from app.core.jwt import JWTManager, get_jwt_manager
from app.models import UserDb
from app.schemas.auth import (
    SendSmsRequest,
    SendSmsResponseForFrontend,
    SigninRequest,
    SignoutRequest,
    SignupRequest,
    VerifySmsRequestFromFrontend,
)
from app.schemas.response import ApiResponse
from app.services.cloudbase_service import CloudbaseService
from app.services.user_service import UserService
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


@router.post("/send_sms")
async def send_sms(
    send_sms_request: SendSmsRequest,
) -> ApiResponse[SendSmsResponseForFrontend]:
    """发送短信验证码"""
    data = await CloudbaseService.send_sms(send_sms_request)
    new_data = SendSmsResponseForFrontend(
        **data.model_dump(exclude_none=True), phone_number=send_sms_request.phone_number
    )
    return ApiResponse.success(data=new_data)


@router.post("/verify_sms")
async def verify_sms(
    verify_sms_request: VerifySmsRequestFromFrontend,
    response: Response,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> ApiResponse[UserDb]:
    """验证短信验证码"""
    data = await CloudbaseService.verify_sms(verify_sms_request)
    verification_token = data.verification_token
    user_service = UserService(db)

    # 如果是新用户，则先注册，否则直接登录
    if verify_sms_request.is_user:
        # 如果是老用户，则直接登录
        token_info = await CloudbaseService.signin(
            SigninRequest(verification_token=verification_token)
        )
    else:
        phone_number = verify_sms_request.phone_number
        token_info = await CloudbaseService.signup(
            SignupRequest(verification_token=verification_token, phone_number=phone_number)
        )

    user = user_service.get_user_by_sub(token_info.sub)
    if not user:
        user = user_service.create_user_from_cloudbase(token_info, verify_sms_request.phone_number)
    else:
        user = user_service.update_user_last_login(user, "sms")

    # 设置自定义响应头
    secret_token_info = jwt_manager.get_payload_with_expiration(
        {**token_info.model_dump(exclude_none=True), "user_id": user.id}
    )
    secret_token_info_str = jwt_manager.create_token(secret_token_info)
    response.headers["x-secret-token-info"] = secret_token_info_str

    return ApiResponse.success(data=user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
) -> ApiResponse[None]:
    """登出"""
    token_info = await get_auth_token_info(request, response)
    await CloudbaseService.signout(SignoutRequest(access_token=token_info.access_token))

    with UserService() as user_service:
        user_service.update_user_last_logout(token_info.user_id)
    return ApiResponse.success(data=None)
