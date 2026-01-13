from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from app.core.config import settings
from app.schemas.config import SecurityConfig
from app.utils.date import get_unix_timestamp


class JWTManager:
    def __init__(self, security: SecurityConfig = settings.security):
        self.algorithm = security.jwt.algorithm
        self.private_key = security.jwt.private_key
        self.public_key = security.jwt.public_key

    def load_private_key(self, key_content: str, password=None):
        """加载私钥（从密钥内容字符串）"""
        if not key_content:
            raise ValueError("Private key content is empty")

        try:
            self.private_key = serialization.load_pem_private_key(
                key_content.encode("utf-8"),
                password=password,
                backend=default_backend(),
            )
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")

    def load_public_key(self, key_content: str):
        """加载公钥（从密钥内容字符串）"""
        if not key_content:
            raise ValueError("Public key content is empty")

        try:
            self.public_key = serialization.load_pem_public_key(
                key_content.encode("utf-8"), backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load public key: {e}")

    def create_token(self, payload_data: dict[str, Any]):
        """创建 JWT token"""
        if not self.private_key:
            raise ValueError("Private key not loaded")

        token = jwt.encode(payload=payload_data, key=self.private_key, algorithm=self.algorithm)

        return token

    def get_payload_with_expiration(self, payload_data: dict[str, Any]):
        """获取 payload 并设置过期时间"""
        now = get_unix_timestamp()
        expiration = now + 35 * 25 * 3600  # 35 天后过期，过期后 refresh_token 也过期，必须重新登录
        payload = {
            **payload_data,
            "exp": expiration,  # 令牌的过期时间
            "iat": now,
        }

        return payload

    def verify_token(self, token: str) -> dict[str, Any]:
        """验证 JWT token"""
        if not self.public_key:
            raise ValueError("Public key not loaded")

        payload = jwt.decode(jwt=token, key=self.public_key, algorithms=[self.algorithm])
        return payload

    def decode_token_without_verification(self, token) -> dict[str, Any]:
        """解码 token 但不验证签名（仅用于调试）"""
        return jwt.decode(token, options={"verify_signature": False})


# 全局单例实例
_jwt_manager: JWTManager | None = None


def get_jwt_manager() -> JWTManager:
    """获取全局 JWTManager 实例（单例模式）

    Returns:
        JWTManager: 全局 JWTManager 实例
    """
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def initialize_jwt_manager() -> JWTManager:
    """初始化全局 JWTManager 实例

    在应用启动时调用，提前加载密钥

    Returns:
        JWTManager: 初始化后的 JWTManager 实例
    """
    return get_jwt_manager()


def get_jwt_manager_dep():
    """FastAPI 依赖注入函数，用于在路由中获取 JWTManager 实例

    使用方式:
        @router.get("/example")
        async def example(jwt_manager: JWTManager = Depends(get_jwt_manager_dep)):
            token = jwt_manager.create_token({"user_id": 123})

    Returns:
        JWTManager: 全局 JWTManager 实例
    """
    return get_jwt_manager()
