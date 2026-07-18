"""
用户认证
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from app.core.cache import invalidate_user
from app.core.db import get_db
from app.core.jwt import JWTManager, get_jwt_manager
from app.models import UserDb
from app.schemas.auth import (
    SendSmsRequest,
    SendSmsResponse,
    SmsLoginRequest,
    WeChatInitResponse,
    WeChatLoginRequest,
)
from app.schemas.response import ApiResponse
from app.services.auth import SmsService, WeChatService
from app.services.user import UserDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.common import gen_uuid
from app.utils.logger import logger

router = APIRouter()


@router.post("/sms/send")
async def send_sms(
    send_sms_request: SendSmsRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[SendSmsResponse]:
    """发送短信验证码（腾讯云短信 + 自建验证码缓存）"""
    data = await SmsService.send_sms(send_sms_request, db)
    return ApiResponse.success(data=data)


@router.post("/sms/login")
async def sms_login(
    sms_login_request: SmsLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> ApiResponse[UserDb]:
    """短信登录（自建验证 + 本系统用户，直接签发 JWT）"""
    user = await SmsService.sms_login(sms_login_request, db)
    if user is not None:
        db.commit()
        await invalidate_user(user.id)
        secret_token_info = jwt_manager.get_payload_with_expiration(
            {
                "user_id": user.id,
                "sub": user.sub or f"sms:{user.phone or ''}",
                "last_login_type": "sms",
            }
        )
        secret_token_info_str = jwt_manager.create_token(secret_token_info)
        response.headers["x-secret-token-info"] = secret_token_info_str
        return ApiResponse.success(data=user)
    raise HTTPException(status_code=500, detail="短信登录未返回用户")


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> ApiResponse[None]:
    """登出（短信用户已无 Cloudbase access_token，不再调用 SmsService.signout）"""
    token_info = await get_auth_token_info(request, jwt_manager)
    UserDbService(db).update_user_last_logout(token_info.user_id)
    db.commit()
    await invalidate_user(token_info.user_id)
    return ApiResponse.success(data=None)


@router.post("/wechat/init")
async def wechat_init() -> ApiResponse[WeChatInitResponse]:
    """微信扫码登录初始化（网站应用 OAuth2.0）"""
    from app.core.config import settings

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
    user_service = UserDbService(db)
    user = user_service.get_or_create_user_by_openid(
        token_data.openid, wechat_user_info
    )
    db.commit()
    await invalidate_user(user.id)

    # 生成 JWT token
    secret_token_info = jwt_manager.get_payload_with_expiration(
        {
            **token_data.model_dump(exclude_none=True),
            "user_id": user.id,
            "sub": token_data.openid,
            "last_login_type": "wechat",
        }
    )
    jwt_token = jwt_manager.create_token(secret_token_info)
    response.headers["x-secret-token-info"] = jwt_token

    logger.info("微信授权成功", openid=token_data.openid, user_id=user.id, state=state)
    return ApiResponse.success(data=user)
