"""
认证相关的 FastAPI 依赖函数
"""

import jwt
from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError

from app.core.jwt import JWTManager, get_jwt_manager
from app.schemas.auth import AuthTokenPayload
from app.utils.logger import logger


def get_auth_token(authorization: str) -> str:
    """从请求头中获取认证令牌"""
    return authorization.replace("Bearer ", "").strip()


def get_user_id_from_token(
    authorization: str | None, jwt_manager: JWTManager | None = None
) -> str | None:
    """从 token 中获取 user_id

    可以在中间件或依赖注入中使用。
    - 在中间件中：需要手动传入 jwt_manager 或从 request.app.state 获取
    - 在依赖注入中：可以使用 Depends(get_jwt_manager) 传入

    Args:
        authorization: Authorization 请求头的值，例如 "Bearer xxx"
        jwt_manager: JWT 管理器实例。如果为 None，则使用 get_jwt_manager() 获取

    Returns:
        user_id 字符串，如果无法获取则返回 None
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    # 如果没有提供 jwt_manager，则获取全局实例
    if jwt_manager is None:
        jwt_manager = get_jwt_manager()

    token = get_auth_token(authorization)
    try:
        payload = jwt_manager.decode_token_without_verification(token)
        return payload.get("user_id")
    except Exception as e:
        logger.error("Failed to get user_id from token", error=e)
        return None


async def get_auth_token_info(
    request: Request,
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> AuthTokenPayload:
    """
    从请求头中解析并验证 JWT token

    功能：
    1. 解析 authorization 头部中的 jwt
    2. 验证 jwt 的签名一致性和过期时间
    3. 如果没有过期，则获取 jwt 中的 user_id

    Args:
        request: FastAPI 请求对象
        jwt_manager: JWT 管理器实例

    Returns:
        token payload

    Raises:
        HTTPException: 当认证失败时
    """
    # 1. 解析 authorization 头部中的 jwt
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    token = get_auth_token(auth_header)

    # 2. 验证 jwt 的签名一致性和过期时间
    try:
        payload = jwt_manager.verify_token(token)
        # 如果没有过期，直接获取 user_id
        if not payload.get("user_id"):
            raise HTTPException(status_code=401, detail="Token 中缺少 user_id")

        return AuthTokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")

    except jwt.InvalidTokenError as e:
        logger.error("Token validation failed", error=e)
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    except ValidationError as e:
        logger.error("Token validation failed", error=e)
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    except Exception as e:
        logger.error("Token processing error", error=e)
        raise HTTPException(status_code=401, detail="认证失败")


async def require_auth(
    request: Request,
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> None:
    """
    只进行认证验证，不返回 token 信息

    用于只需要确保用户已认证但不需要使用 token 数据的接口。
    这个函数会执行完整的 token 验证流程，但不返回任何数据。

    Args:
        request: FastAPI 请求对象
        response: FastAPI 响应对象
        jwt_manager: JWT 管理器实例

    Raises:
        HTTPException: 当认证失败时
    """
    # 调用完整的认证流程，但不使用返回值
    await get_auth_token_info(request, jwt_manager)
