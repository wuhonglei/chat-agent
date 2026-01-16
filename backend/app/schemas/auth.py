from pydantic import BaseModel, Field


class SendSmsRequest(BaseModel):
    """Send SMS request"""

    phone_number: str = Field(..., description="Phone number")
    target: str = Field("ANY", description="Target")


class SendSmsResponse(BaseModel):
    """Send SMS response"""

    verification_id: str = Field(..., description="Verification ID")
    expires_in: int = Field(..., description="Expires in")
    is_user: bool = Field(False, description="Is user registered in the cloudbase")


class SendSmsResponseForFrontend(SendSmsResponse):
    """Send SMS response for frontend"""

    phone_number: str = Field(..., description="Phone number")


class VerifySmsRequest(BaseModel):
    """Verify SMS request"""

    verification_id: str = Field(..., description="Verification ID")
    verification_code: str = Field(..., description="Verification code")


class VerifySmsRequestFromFrontend(VerifySmsRequest):
    """Verify SMS request from frontend"""

    phone_number: str = Field(..., description="Phone number")
    is_user: bool = Field(False, description="Is user registered in the cloudbase")


class VerifySmsResponse(BaseModel):
    """Verify SMS response"""

    verification_token: str = Field(..., description="Verification token")
    expires_in: int = Field(..., description="Expires in")


class SigninRequest(BaseModel):
    """Signin request"""

    verification_token: str = Field(..., description="Verification token")


class SigninResponse(BaseModel):
    """Signin response"""

    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    expires_in: int = Field(..., description="Expires in")
    token_type: str = Field("Bearer", description="Token type")
    sub: str = Field(..., description="User Id in the cloudbase")


class SignupRequest(BaseModel):
    """Signup request"""

    phone_number: str = Field(..., description="Phone number")
    verification_token: str = Field(..., description="Verification token")


class SignupResponse(SigninResponse):
    """Signup response"""

    pass


class SignoutRequest(BaseModel):
    """Sign out request"""

    access_token: str = Field(..., description="Access token")


class SignoutResponse(BaseModel):
    """Sign out response"""

    redirect_uri: str | None = Field(None, description="Redirect URI")


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., description="Refresh token")
    grant_type: str = Field("refresh_token", description="Grant type")


class RefreshTokenResponse(SigninResponse):
    """Refresh token response"""

    pass


class WeChatInitRequest(BaseModel):
    """微信扫码登录初始化请求"""

    old_state: str | None = Field(None, description="旧的状态参数")


class WeChatInitResponse(BaseModel):
    """微信扫码登录初始化响应（网站应用）"""

    authorize_url: str = Field(..., description="授权 URL（用于生成二维码）")
    appid: str = Field(..., description="微信开放平台 AppID")
    redirect_uri: str = Field(..., description="授权回调地址")
    state: str = Field(..., description="状态参数，用于标识登录请求和防止 CSRF")
    expire_seconds: int = Field(
        default=600, description="状态过期时间（秒），默认 600 秒"
    )


class WeChatCheckRequest(BaseModel):
    """微信扫码登录状态检测请求（网站应用）"""

    state: str = Field(..., description="状态参数")


class WeChatCheckResponse(BaseModel):
    """微信扫码登录状态检测响应"""

    status: str = Field(
        ...,
        description="登录状态: waiting(等待扫码), scanned(已扫码), confirmed(已确认), expired(已过期)",
    )
    user: dict | None = Field(None, description="用户信息（仅在 confirmed 状态时返回）")


class WechatCallbackData(BaseModel):
    """微信回调数据模型"""

    ToUserName: str = Field(..., description="开发者微信号")
    FromUserName: str = Field(..., description="发送方账号（OpenID）")
    CreateTime: int = Field(..., description="消息创建时间")
    MsgType: str = Field(..., description="消息类型")
    Event: str | None = Field(None, description="事件类型")
    EventKey: str | None = Field(None, description="事件 KEY 值")
    Ticket: str | None = Field(None, description="二维码的 ticket")
