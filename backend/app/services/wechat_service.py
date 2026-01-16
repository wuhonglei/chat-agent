"""微信服务

用于调用微信开放平台网站应用 API（OAuth2.0 授权登录）
"""

import time
import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.utils.logger import logger

# 内存状态存储字典
# Key: ticket 或 scene_str
# Value: 状态信息字典 {status, openid, user_id, jwt_token, created_at, expire_at}
_wechat_login_states: dict[str, dict[str, Any]] = {}

# access_token 缓存
_access_token_cache: dict[str, Any] = {}


class WeChatService:
    """微信服务类（微信开放平台网站应用）"""

    VERIFY_SSL = not settings.app.debug  # 如果DEBUG为True，则不验证SSL证书
    BASE_URL = "https://api.weixin.qq.com"
    OPEN_URL = "https://open.weixin.qq.com"

    @staticmethod
    def generate_authorize_url(state: str) -> str:
        """生成微信开放平台授权 URL（网站应用扫码登录）

        Args:
            state: 状态参数，用于防止 CSRF 攻击

        Returns:
            授权 URL
        """
        from urllib.parse import quote

        redirect_uri = quote(
            "https://chat.wuhonglei.cn/api/auth/wechat/callback", safe=""
        )
        authorize_url = (
            f"{WeChatService.OPEN_URL}/connect/qrconnect"
            f"?appid={settings.wechat.app_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=snsapi_login"
            f"&state={state}"
            f"#wechat_redirect"
        )
        return authorize_url

    @staticmethod
    async def get_access_token_by_code(code: str) -> dict[str, Any]:
        """通过 code 换取 access_token（网站应用 OAuth2.0）

        Args:
            code: 授权码

        Returns:
            包含 access_token、openid 等的字典

        Raises:
            HTTPException: 当获取失败时
        """
        url = f"{WeChatService.BASE_URL}/sns/oauth2/access_token"
        params = {
            "appid": settings.wechat.app_id,
            "secret": settings.wechat.app_secret,
            "code": code,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(verify=WeChatService.VERIFY_SSL) as client:
            try:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    if "access_token" in data:
                        logger.info("微信 access_token 获取成功（通过 code）")
                        return data
                    else:
                        error_msg = data.get("errmsg", "未知错误")
                        error_code = data.get("errcode", -1)
                        logger.error(
                            "微信通过 code 获取 access_token 失败",
                            error_code=error_code,
                            error_msg=error_msg,
                        )
                        raise HTTPException(
                            status_code=500,
                            detail=f"获取微信 access_token 失败: {error_msg}",
                        )
                else:
                    logger.error(
                        f"微信获取 access_token 失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"获取微信 access_token 失败: {response.text}",
                    )
            except httpx.RequestError as e:
                logger.error("微信获取 access_token 请求失败", error=e)
                raise HTTPException(status_code=500, detail="微信服务暂时不可用")

    @staticmethod
    async def get_user_info(openid: str, access_token: str) -> dict[str, Any]:
        """获取微信用户信息（网站应用 OAuth2.0）

        Args:
            openid: 用户的 openid
            access_token: OAuth2.0 access_token

        Returns:
            用户信息字典

        Raises:
            HTTPException: 当获取失败时
        """
        url = f"{WeChatService.BASE_URL}/sns/userinfo"
        params = {
            "access_token": access_token,
            "openid": openid,
            "lang": "zh_CN",
        }

        async with httpx.AsyncClient(verify=WeChatService.VERIFY_SSL) as client:
            try:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    if "openid" in data:
                        logger.info("微信用户信息获取成功", openid=openid)
                        return data
                    else:
                        error_msg = data.get("errmsg", "未知错误")
                        error_code = data.get("errcode", -1)
                        logger.error(
                            "微信获取用户信息失败",
                            error_code=error_code,
                            error_msg=error_msg,
                            openid=openid,
                        )
                        raise HTTPException(
                            status_code=500,
                            detail=f"获取微信用户信息失败: {error_msg}",
                        )
                else:
                    logger.error(
                        f"微信获取用户信息失败: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"获取微信用户信息失败: {response.text}",
                    )
            except httpx.RequestError as e:
                logger.error("微信获取用户信息请求失败", error=e)
                raise HTTPException(status_code=500, detail="微信服务暂时不可用")

    @staticmethod
    def init_login_state(state: str, expire_seconds: int = 600) -> None:
        """初始化登录状态（网站应用使用 state 参数）

        Args:
            state: 状态参数（用于防止 CSRF）
            expire_seconds: 过期时间（秒），默认 600 秒（10分钟）
        """
        now = int(time.time())
        expire_at = now + expire_seconds + 60  # 额外 60 秒缓冲

        login_state = {
            "status": "waiting",
            "state": state,
            "created_at": now,
            "expire_at": expire_at,
        }

        _wechat_login_states[state] = login_state

    @staticmethod
    def get_login_state(state: str) -> dict[str, Any] | None:
        """获取登录状态

        Args:
            state: 状态参数

        Returns:
            状态字典，如果不存在或已过期返回 None
        """
        login_state = _wechat_login_states.get(state)
        if not login_state:
            return None

        # 检查是否过期
        now = int(time.time())
        if login_state.get("expire_at", 0) < now:
            # 清理过期状态
            if state in _wechat_login_states:
                del _wechat_login_states[state]
            return None

        return login_state

    @staticmethod
    def update_login_state(
        state: str,
        status: str,
        openid: str | None = None,
        user_id: str | None = None,
        jwt_token: str | None = None,
    ) -> None:
        """更新登录状态

        Args:
            state: 状态参数
            status: 状态值（waiting, scanned, confirmed, expired）
            openid: 用户 openid（可选）
            user_id: 用户 ID（可选）
            jwt_token: JWT token（可选）
        """
        login_state = _wechat_login_states.get(state)
        if not login_state:
            return

        login_state["status"] = status
        if openid:
            login_state["openid"] = openid
        if user_id:
            login_state["user_id"] = user_id
        if jwt_token:
            login_state["jwt_token"] = jwt_token

    @staticmethod
    def clear_login_state(state: str | None) -> None:
        """清除登录状态

        Args:
            state: 状态参数
        """
        if state and state in _wechat_login_states:
            del _wechat_login_states[state]

    @staticmethod
    def generate_scene_str() -> str:
        """生成唯一的场景值字符串

        Returns:
            场景值字符串（UUID）
        """
        return str(uuid.uuid4())
