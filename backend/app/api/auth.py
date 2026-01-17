"""
用户认证
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.jwt import JWTManager, get_jwt_manager
from app.models import UserDb
from app.schemas.auth import (
    SendSmsRequest,
    SendSmsResponseForFrontend,
    SigninRequest,
    SignoutRequest,
    SignupRequest,
    SmsLoginRequestFromFrontend,
    WeChatInitResponse,
    WeChatLoginRequest,
)
from app.schemas.response import ApiResponse
from app.services.cloudbase_service import CloudbaseService
from app.services.user_service import UserService
from app.services.wechat_service import WeChatService
from app.utils.auth_deps import get_auth_token_info
from app.utils.common import gen_uuid
from app.utils.logger import logger

router = APIRouter()


@router.post("/sms/send")
async def send_sms(
    send_sms_request: SendSmsRequest,
) -> ApiResponse[SendSmsResponseForFrontend]:
    """发送短信验证码"""
    data = await CloudbaseService.send_sms(send_sms_request)
    new_data = SendSmsResponseForFrontend(
        **data.model_dump(exclude_none=True), phone_number=send_sms_request.phone_number
    )
    return ApiResponse.success(data=new_data)


@router.post("/sms/login")
async def sms_login(
    sms_login_request: SmsLoginRequestFromFrontend,
    response: Response,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> ApiResponse[UserDb]:
    """短信登录"""
    data = await CloudbaseService.sms_login(sms_login_request)
    verification_token = data.verification_token
    user_service = UserService(db)

    # 如果是新用户，则先注册，否则直接登录
    if sms_login_request.is_user:
        # 如果是老用户，则直接登录
        token_info = await CloudbaseService.signin(
            SigninRequest(verification_token=verification_token)
        )
    else:
        phone_number = sms_login_request.phone_number
        token_info = await CloudbaseService.signup(
            SignupRequest(
                verification_token=verification_token, phone_number=phone_number
            )
        )

    user = user_service.get_user_by_sub(token_info.sub)
    if not user:
        user = user_service.create_user_from_cloudbase(
            token_info, sms_login_request.phone_number
        )
    else:
        user = user_service.update_user_last_login(user, "sms")

    # 设置自定义响应头
    secret_token_info = jwt_manager.get_payload_with_expiration(
        {
            **token_info.model_dump(exclude_none=True),
            "user_id": user.id,
            "sub": token_info.sub,
        }
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


@router.post("/wechat/init")
async def wechat_init() -> ApiResponse[WeChatInitResponse]:
    """微信扫码登录初始化（网站应用 OAuth2.0）"""

    # 生成唯一的 state 参数（用于防止 CSRF 攻击）
    state = gen_uuid()
    response_data = WeChatInitResponse(
        appid=settings.wechat.app_id,
        state=state,
    )

    return ApiResponse.success(data=response_data)


@router.post("/wechat/login")
async def wechat_callback(
    wechat_login_request: WeChatLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> ApiResponse[UserDb]:
    """微信授权回调接口（网站应用 OAuth2.0）

    微信授权后会跳转到此接口，并带上 code 和 state 参数
    """
    code = wechat_login_request.code
    state = wechat_login_request.state
    if not code or not state:
        logger.warning("微信回调缺少必要参数", code=code, state=state)
        raise HTTPException(status_code=401, detail="微信回调缺少必要参数")

    # 通过 code 换取 access_token
    token_data = await WeChatService.get_access_token_by_code(code)

    # 获取用户信息
    wechat_user_info = await WeChatService.get_user_info(
        token_data.openid, token_data.access_token
    )

    # 创建或更新用户
    user_service = UserService(db)
    user = user_service.get_or_create_user_by_openid(
        token_data.openid, wechat_user_info
    )

    # 生成 JWT token
    secret_token_info = jwt_manager.get_payload_with_expiration(
        {
            **token_data.model_dump(exclude_none=True),
            "user_id": user.id,
            "sub": token_data.openid,
        }
    )
    jwt_token = jwt_manager.create_token(secret_token_info)
    response.headers["x-secret-token-info"] = jwt_token

    logger.info("微信授权成功", openid=token_data.openid, user_id=user.id, state=state)
    return ApiResponse.success(data=user)
