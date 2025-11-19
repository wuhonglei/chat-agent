"""认证辅助函数

用于处理 Cloudbase token 和服务端 token 之间的转换
"""

import jwt
from datetime import timedelta
from typing import Dict, Any
from app.utils.jwt_auth import JWTAuth
from app.core.config import settings


def create_server_tokens(cloudbase_response: Dict[str, Any]) -> Dict[str, Any]:
    """将 Cloudbase 的 token 转换为服务端 token

    Args:
        cloudbase_response: Cloudbase 返回的响应，包含 access_token 和 refresh_token

    Returns:
        包含服务端签名的 access_token 和 refresh_token 的字典
    """
    # 解析 Cloudbase 的 access_token 获取用户 ID（不验证签名，仅用于提取信息）
    cloudbase_token = cloudbase_response.get('access_token')
    if not cloudbase_token:
        raise ValueError("Cloudbase response 中缺少 access_token")

    try:
        decoded = jwt.decode(cloudbase_token, options={
                             "verify_signature": False})
        user_id = decoded.get('sub')
        if not user_id:
            raise ValueError("Cloudbase token 中缺少用户 ID (sub)")
    except jwt.DecodeError as e:
        raise ValueError(f"无法解析 Cloudbase token: {str(e)}")

    # 创建服务端的 access_token
    server_access_token = JWTAuth.create_access_token(
        user_id=user_id,
        cloudbase_access_token=cloudbase_response['access_token'],
        cloudbase_refresh_token=cloudbase_response.get('refresh_token', ''),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # 创建服务端的 refresh_token
    server_refresh_token = JWTAuth.create_refresh_token(
        user_id=user_id,
        cloudbase_refresh_token=cloudbase_response.get('refresh_token', ''),
        expires_delta=timedelta(days=7)  # refresh_token 有效期 7 天
    )

    return {
        "access_token": server_access_token,
        "refresh_token": server_refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
