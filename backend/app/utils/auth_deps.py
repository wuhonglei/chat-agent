"""
认证相关的 FastAPI 依赖函数
"""

from fastapi import Request, Response, HTTPException, Depends
from loguru import logger
import jwt
from app.jwt.jwt_manager import JWTManager, get_jwt_manager
from app.models.auth import RefreshTokenRequest
from app.models.token import SecretTokenInfo
from app.services.cloudbase_service import CloudbaseService


async def get_auth_token_info(
    request: Request,
    response: Response,
    jwt_manager: JWTManager = Depends(get_jwt_manager)
) -> SecretTokenInfo:
    """
    从请求头中解析并验证 JWT token，支持自动刷新

    功能：
    1. 解析 authorization 头部中的 jwt
    2. 验证 jwt 的签名一致性
    3. 判断 jwt 是否过期，如果过期则使用 jwt 中的 refresh token 刷新 access token
    4. 如果没有过期，则获取 jwt 中的 user_id

    Args:
        request: FastAPI 请求对象
        response: FastAPI 响应对象
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

    token = auth_header.replace("Bearer ", "").strip()

    # 2. 验证 jwt 的签名一致性和过期时间
    try:
        payload = jwt_manager.verify_token(token)
        # 如果没有过期，直接获取 user_id
        if not payload.get("user_id"):
            raise HTTPException(status_code=401, detail="Token 中缺少 user_id")
        return SecretTokenInfo(**payload)

    except jwt.ExpiredSignatureError:
        # 3. 如果过期，使用 refresh_token 刷新 access token
        logger.info("Token 已过期，尝试使用 refresh_token 刷新")

        # 先解码 token（不验证签名）以获取 refresh_token
        try:
            expired_payload = jwt_manager.decode_token_without_verification(
                token)
            refresh_token = expired_payload.get("refresh_token")

            if not refresh_token:
                raise HTTPException(
                    status_code=401, detail="Token 已过期且缺少 refresh_token，请重新登录")

            # 从过期 token 中获取 user_id（如果存在）
            user_id = expired_payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=401, detail="无法从过期 token 中获取 user_id")

            # 使用 refresh_token 刷新 access token
            refresh_request = RefreshTokenRequest(refresh_token=refresh_token)
            new_token_info = await CloudbaseService.refresh_token(refresh_request)

            # 生成新的 JWT token
            new_payload = {
                **new_token_info.model_dump(exclude_none=True),
                "user_id": user_id
            }

            new_secret_token_info = jwt_manager.get_payload_with_expiration(
                new_payload,
                new_token_info.expires_in
            )
            new_secret_token_info = jwt_manager.create_token(
                new_secret_token_info)

            # 在响应头中返回新的 token
            response.headers["x-secret-token-info"] = new_secret_token_info
            logger.info(f"Token 刷新成功，user_id: {user_id}")

            return SecretTokenInfo(**new_secret_token_info)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token 刷新失败: {e}")
            raise HTTPException(status_code=401, detail="Token 刷新失败，请重新登录")

    except jwt.InvalidTokenError as e:
        logger.error(f"Token 验证失败: {e}")
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    except Exception as e:
        logger.error(f"Token 处理异常: {e}")
        raise HTTPException(status_code=401, detail="认证失败")


async def require_auth(
    request: Request,
    response: Response,
    jwt_manager: JWTManager = Depends(get_jwt_manager)
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
    await get_auth_token_info(request, response, jwt_manager)
