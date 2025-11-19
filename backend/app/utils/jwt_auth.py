"""JWT 认证工具类

用于生成和验证服务端自己的 JWT token
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException
from app.core.config import settings


class JWTAuth:
    """JWT 认证工具类"""

    @staticmethod
    def create_access_token(
        user_id: str,
        cloudbase_access_token: str,
        cloudbase_refresh_token: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建服务端的 access token

        Args:
            user_id: 用户 ID（从 Cloudbase token 中解析）
            cloudbase_access_token: Cloudbase 的原始 access_token（用于后续调用 Cloudbase API）
            cloudbase_refresh_token: Cloudbase 的原始 refresh_token（用于刷新 token）
            expires_delta: 过期时间间隔，默认使用配置中的 ACCESS_TOKEN_EXPIRE_MINUTES
            additional_claims: 额外的 JWT claims（如用户角色、权限等）

        Returns:
            服务端签名的 JWT token
        """
        if expires_delta is None:
            expires_delta = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": user_id,  # subject (用户 ID)
            "exp": expire,  # expiration time
            "iat": datetime.utcnow(),  # issued at
            "type": "access",
            # 保存 Cloudbase 的原始 token（加密存储，仅服务端使用）
            "cloudbase_access_token": cloudbase_access_token,
            "cloudbase_refresh_token": cloudbase_refresh_token,
        }

        # 添加额外的 claims
        if additional_claims:
            payload.update(additional_claims)

        encoded_jwt = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        user_id: str,
        cloudbase_refresh_token: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建服务端的 refresh token

        Args:
            user_id: 用户 ID
            cloudbase_refresh_token: Cloudbase 的原始 refresh_token
            expires_delta: 过期时间间隔，默认 7 天

        Returns:
            服务端签名的 refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=7)

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "cloudbase_refresh_token": cloudbase_refresh_token,
        }

        encoded_jwt = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """验证并解析 JWT token

        Args:
            token: JWT token 字符串
            token_type: token 类型 ("access" 或 "refresh")

        Returns:
            解析后的 payload

        Raises:
            HTTPException: 当 token 无效或过期时
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            # 验证 token 类型
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=401,
                    detail=f"Token 类型不匹配，期望 {token_type}"
                )

            # 检查是否过期（jwt.decode 会自动检查 exp，但我们可以额外验证）
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(status_code=401, detail="Token 已过期")

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token 已过期")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"无效的 Token: {str(e)}")

    @staticmethod
    def get_user_id_from_token(token: str) -> str:
        """从 token 中提取用户 ID

        Args:
            token: JWT token

        Returns:
            用户 ID
        """
        payload = JWTAuth.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 中缺少用户信息")
        return user_id

    @staticmethod
    def get_cloudbase_tokens_from_token(token: str) -> tuple[str, str]:
        """从 token 中提取 Cloudbase 的原始 token

        Args:
            token: JWT token

        Returns:
            (cloudbase_access_token, cloudbase_refresh_token)
        """
        payload = JWTAuth.verify_token(token)
        access_token = payload.get("cloudbase_access_token")
        refresh_token = payload.get("cloudbase_refresh_token")

        if not access_token or not refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Token 中缺少 Cloudbase 认证信息"
            )

        return access_token, refresh_token
