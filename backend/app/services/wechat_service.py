"""微信服务

用于调用微信开放平台网站应用 API（OAuth2.0 授权登录）
"""

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.auth import WeChatAccessTokenResponse, WeChatUserInfoResponse
from app.utils.logger import logger


class WeChatService:
    """微信服务类（微信开放平台网站应用）"""

    VERIFY_SSL = not settings.app.debug  # 如果DEBUG为True，则不验证SSL证书
    BASE_URL = "https://api.weixin.qq.com"

    @staticmethod
    async def get_access_token_by_code(code: str) -> WeChatAccessTokenResponse:
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
                        return WeChatAccessTokenResponse.model_validate(data)
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
    async def get_user_info(openid: str, access_token: str) -> WeChatUserInfoResponse:
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
                        return WeChatUserInfoResponse.model_validate(data)
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
