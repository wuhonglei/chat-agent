"""认证依赖注入函数

用于 FastAPI 的依赖注入，自动处理 token 验证和刷新
"""

import os
import httpx
from fastapi import HTTPException, Request, Response
from typing import Optional, Dict, Any
from app.utils.jwt_auth import JWTAuth
from app.utils.auth_helper import create_server_tokens
from app.core.config import settings
from loguru import logger


async def get_current_user_with_auto_refresh(
    request: Request,
    response: Response
) -> Dict[str, Any]:
    """获取当前用户，自动处理 token 刷新

    如果 access_token 过期，会自动使用 refresh_token 刷新，
    并在响应头中返回新的 token。

    Args:
        request: FastAPI Request 对象
        response: FastAPI Response 对象，用于设置新的 token

    Returns:
        包含用户信息的字典

    Raises:
        HTTPException: 当 token 无效或刷新失败时
    """
    auth_header = request.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    access_token = auth_header.replace('Bearer ', '')

    try:
        # 尝试验证 access_token
        payload = JWTAuth.verify_token(access_token, token_type="access")
        return payload
    except HTTPException as e:
        # 如果 access_token 过期，尝试使用 refresh_token 刷新
        if e.status_code == 401 and "过期" in str(e.detail):
            # 从请求头或 Cookie 中获取 refresh_token
            refresh_token = _get_refresh_token_from_request(request)
            if not refresh_token:
                raise HTTPException(
                    status_code=401,
                    detail="Access token 已过期，且未提供 refresh token"
                )

            try:
                # 验证 refresh_token
                refresh_payload = JWTAuth.verify_token(
                    refresh_token,
                    token_type="refresh"
                )

                # 使用 Cloudbase 的 refresh_token 获取新的 token
                cloudbase_refresh_token = refresh_payload.get(
                    "cloudbase_refresh_token"
                )
                new_cloudbase_tokens = await _refresh_cloudbase_token(
                    cloudbase_refresh_token
                )

                # 重新签名生成新的服务端 token
                new_server_tokens = create_server_tokens(new_cloudbase_tokens)

                # 在响应头中返回新的 token
                response.headers["X-New-Access-Token"] = new_server_tokens[
                    "access_token"
                ]
                response.headers["X-New-Refresh-Token"] = new_server_tokens[
                    "refresh_token"
                ]

                logger.info(
                    f"Token 自动刷新成功，用户 ID: {refresh_payload.get('sub')}"
                )

                return {
                    "user_id": refresh_payload.get("sub"),
                    "cloudbase_access_token": new_cloudbase_tokens[
                        "access_token"
                    ],
                    "cloudbase_refresh_token": new_cloudbase_tokens[
                        "refresh_token"
                    ],
                }
            except HTTPException:
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token 无效或已过期，请重新登录"
                )
        else:
            raise


def _get_refresh_token_from_request(request: Request) -> Optional[str]:
    """从请求中获取 refresh_token

    优先从 X-Refresh-Token header 中获取，
    其次从 Cookie 中获取。

    Args:
        request: FastAPI Request 对象

    Returns:
        refresh_token 字符串，如果未找到则返回 None
    """
    # 方式1: 从 X-Refresh-Token header 获取
    refresh_token = request.headers.get("X-Refresh-Token")
    if refresh_token:
        return refresh_token

    # 方式2: 从 Cookie 获取
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        return refresh_token

    return None


async def _refresh_cloudbase_token(
    cloudbase_refresh_token: str
) -> Dict[str, Any]:
    """调用 Cloudbase API 刷新 token

    Args:
        cloudbase_refresh_token: Cloudbase 的 refresh_token

    Returns:
        Cloudbase 返回的新 token 信息

    Raises:
        HTTPException: 当刷新失败时
    """
    # 从配置或环境变量中获取 env_id
    env_id = getattr(settings, "CLOUDBASE_ENV_ID",
                     None) or os.environ.get("env_id")
    if not env_id:
        raise HTTPException(
            status_code=500,
            detail="Cloudbase 环境 ID 未配置，请设置 CLOUDBASE_ENV_ID 或 env_id 环境变量"
        )

    url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/token"

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": cloudbase_refresh_token,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Cloudbase token 刷新失败: {response.status_code}, "
                    f"{response.text}"
                )
                raise HTTPException(
                    status_code=401,
                    detail="Token 刷新失败，请重新登录"
                )
        except httpx.RequestError as e:
            logger.error(f"Cloudbase token 刷新请求失败: {e}")
            raise HTTPException(
                status_code=500,
                detail="认证服务暂时不可用"
            )


async def get_current_user(request: Request) -> Dict[str, Any]:
    """获取当前用户（不自动刷新 token）

    用于不需要自动刷新 token 的场景，或者手动处理刷新的场景。

    Args:
        request: FastAPI Request 对象

    Returns:
        包含用户信息的字典

    Raises:
        HTTPException: 当 token 无效时
    """
    auth_header = request.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    token = auth_header.replace('Bearer ', '')
    payload = JWTAuth.verify_token(token, token_type="access")

    return {
        "user_id": payload.get("sub"),
        "cloudbase_access_token": payload.get("cloudbase_access_token"),
        "cloudbase_refresh_token": payload.get("cloudbase_refresh_token"),
    }
