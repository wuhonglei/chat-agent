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
    WechatCheckRequest,
    WechatCheckResponse,
    WechatInitResponse,
)
from app.schemas.response import ApiResponse
from app.services.cloudbase_service import CloudbaseService
from app.services.user_service import UserService
from app.services.wechat_service import WechatService
from app.utils.auth_deps import get_auth_token_info
from app.utils.logger import logger

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
            SignupRequest(
                verification_token=verification_token, phone_number=phone_number
            )
        )

    user = user_service.get_user_by_sub(token_info.sub)
    if not user:
        user = user_service.create_user_from_cloudbase(
            token_info, verify_sms_request.phone_number
        )
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


@router.post("/wechat/init")
async def wechat_init() -> ApiResponse[WechatInitResponse]:
    """微信扫码登录初始化（网站应用 OAuth2.0）"""
    # 生成唯一的 state 参数（用于防止 CSRF 攻击）
    state = WechatService.generate_scene_str()

    # 生成授权 URL
    authorize_url = WechatService.generate_authorize_url(state)

    # 初始化状态（默认 10 分钟过期）
    expire_seconds = 600
    WechatService.init_login_state(state, expire_seconds)

    response_data = WechatInitResponse(
        authorize_url=authorize_url,
        state=state,
        expire_seconds=expire_seconds,
    )

    return ApiResponse.success(data=response_data)


@router.post("/wechat/check")
async def wechat_check(
    check_request: WechatCheckRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[WechatCheckResponse]:
    """微信扫码登录状态检测（网站应用）"""
    state = check_request.state
    login_state = WechatService.get_login_state(state)

    if not login_state:
        return ApiResponse.success(
            data=WechatCheckResponse(status="expired", user=None)
        )

    status = login_state.get("status", "waiting")

    # 如果已确认，返回用户信息和 JWT token
    if status == "confirmed":
        user_id = login_state.get("user_id")
        jwt_token = login_state.get("jwt_token")

        if user_id and jwt_token:
            # 设置自定义响应头
            response.headers["x-secret-token-info"] = jwt_token

            # 获取用户信息
            user_service = UserService(db)
            user = user_service.get_user(user_id)
            if user:
                user_dict = {
                    "id": user.id,
                    "name": user.name,
                    "avatar": user.avatar,
                    "email": user.email,
                    "phone": user.phone,
                }
                return ApiResponse.success(
                    data=WechatCheckResponse(status="confirmed", user=user_dict)
                )

    return ApiResponse.success(data=WechatCheckResponse(status=status, user=None))


@router.get("/wechat/callback")
async def wechat_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> str:
    """微信授权回调接口（网站应用 OAuth2.0）

    微信授权后会跳转到此接口，并带上 code 和 state 参数
    """
    if not code or not state:
        logger.warning("微信回调缺少必要参数", code=code, state=state)
        # 返回错误页面或重定向到前端错误页面
        return "授权失败：缺少必要参数"

    # 验证 state 是否存在
    login_state = WechatService.get_login_state(state)
    if not login_state:
        logger.warning("微信回调 state 不存在或已过期", state=state)
        return "授权失败：state 无效或已过期"

    try:
        # 通过 code 换取 access_token
        token_data = await WechatService.get_access_token_by_code(code)
        access_token = token_data["access_token"]
        openid = token_data["openid"]

        # 更新状态为已扫码
        WechatService.update_login_state(state, "scanned", openid=openid)

        # 获取用户信息
        wechat_user_info = await WechatService.get_user_info(openid, access_token)

        # 创建或更新用户
        user_service = UserService(db)
        user = user_service.get_or_create_user_by_openid(openid, wechat_user_info)

        # 生成 JWT token
        secret_token_info = jwt_manager.get_payload_with_expiration(
            {
                "openid": openid,
                "user_id": user.id,
                "sub": openid,  # 兼容现有字段
            }
        )
        jwt_token = jwt_manager.create_token(secret_token_info)

        # 更新状态为已确认
        WechatService.update_login_state(
            state,
            "confirmed",
            openid=openid,
            user_id=user.id,
            jwt_token=jwt_token,
        )

        logger.info("微信授权成功", openid=openid, user_id=user.id, state=state)

        # 重定向到前端页面（前端页面会轮询 /wechat/check 获取登录状态）
        # 这里返回一个简单的 HTML 页面，提示用户关闭窗口或自动关闭
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>授权成功</title>
        </head>
        <body>
            <h2>授权成功！</h2>
            <p>请关闭此窗口，返回应用继续操作。</p>
            <script>
                // 可选：自动关闭窗口（如果是从弹窗打开的）
                setTimeout(function() {
                    window.close();
                }, 2000);
            </script>
        </body>
        </html>
        """

    except Exception as e:
        logger.error("微信回调处理失败", error=e, code=code, state=state)
        return f"授权失败：{str(e)}"
