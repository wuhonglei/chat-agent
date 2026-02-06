from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthTokenPayload(BaseModel):
    """JWT 解析后的认证载荷，与 create_token 时写入的 payload 结构一致"""

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(..., description="User ID")
    iat: int = Field(..., description="Issued at")
    exp: int = Field(..., description="Expires at")
    sub: str | None = Field(default=None, description="Subject")
    last_login_type: Literal["sms", "wechat"] | None = Field(
        default=None, description="Last login type"
    )


class SendSmsRequest(BaseModel):
    """Send SMS request"""

    phone_number: str = Field(..., description="Phone number")
    target: str = Field("ANY", description="Target")


class SendSmsResponse(BaseModel):
    """Send SMS response"""

    verification_id: str = Field(..., description="Verification ID")
    expires_in: int = Field(..., description="Expires in")
    phone_number: str = Field(..., description="Phone number")


class SmsLoginRequest(BaseModel):
    """Sms login request"""

    verification_id: str = Field(..., description="Verification ID")
    verification_code: str = Field(..., description="Verification code")
    phone_number: str = Field(..., description="Phone number")


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


class WeChatInitResponse(BaseModel):
    """微信扫码登录初始化响应（网站应用）"""

    appid: str = Field(..., description="微信开放平台 AppID")
    state: str = Field(..., description="状态参数，用于标识登录请求和防止 CSRF")


class WeChatCheckRequest(BaseModel):
    """微信扫码登录状态检测请求（网站应用）"""

    state: str = Field(..., description="状态参数")


class WeChatCheckResponse(BaseModel):
    """微信扫码登录状态检测响应"""

    status: str = Field(
        ...,
        description="登录状态: waiting(等待扫码), scanned(已扫码), confirmed(已确认), expired(已过期)",
    )
    user: dict[str, Any] | None = Field(
        None, description="用户信息（仅在 confirmed 状态时返回）"
    )


class WechatCallbackData(BaseModel):
    """微信回调数据模型"""

    ToUserName: str = Field(..., description="开发者微信号")
    FromUserName: str = Field(..., description="发送方账号（OpenID）")
    CreateTime: int = Field(..., description="消息创建时间")
    MsgType: str = Field(..., description="消息类型")
    Event: str | None = Field(None, description="事件类型")
    EventKey: str | None = Field(None, description="事件 KEY 值")
    Ticket: str | None = Field(None, description="二维码的 ticket")


class WeChatLoginRequest(BaseModel):
    """微信扫码登录请求"""

    code: str = Field(..., description="授权码")
    state: str = Field(..., description="状态参数")


class WeChatAccessTokenResponse(BaseModel):
    """微信 access_token 接口响应"""

    access_token: str = Field(..., description="网页授权接口调用凭证")
    expires_in: int = Field(
        ..., description="access_token接口调用凭证超时时间，单位（秒）"
    )
    refresh_token: str = Field(..., description="用户刷新access_token")
    openid: str = Field(..., description="用户唯一标识")
    scope: str = Field(..., description="用户授权的作用域，使用逗号（,）分隔")
    unionid: str = Field(
        ...,
        description="当且仅当该网站应用已获得该用户的userinfo授权时，才会出现该字段",
    )


class WeChatUserInfoResponse(BaseModel):
    """微信用户信息接口响应"""

    openid: str = Field(..., description="用户的唯一标识")
    nickname: str = Field(..., description="用户昵称")
    sex: int = Field(
        ..., description="用户的性别，值为1时是男性，值为2时是女性，值为0时是未知"
    )
    province: str | None = Field(None, description="用户个人资料填写的省份")
    city: str | None = Field(None, description="普通用户个人资料填写的城市")
    country: str | None = Field(None, description="国家，如中国为CN")
    headimgurl: str = Field(
        ...,
        description="用户头像，最后一个数值代表正方形头像大小（有0、46、64、96、132数值可选，0代表640*640正方形头像），用户没有头像时该项为空。若用户更换头像，原有头像URL将失效",
    )
    privilege: list[str] | None = Field(
        None, description="用户特权信息，json 数组，如微信沃卡用户为（chinaunicom）"
    )
    unionid: str | None = Field(
        None, description="只有在用户将公众号绑定到微信开放平台帐号后，才会出现该字段"
    )


class SmsVerificationEntry(BaseModel):
    """Sms verification entry"""

    code: str = Field(..., description="Verification code")
    phone: str = Field(..., description="Phone number")
    expires_at: float = Field(..., description="Expires at")
