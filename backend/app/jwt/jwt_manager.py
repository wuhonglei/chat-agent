from datetime import timedelta
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from app.core.config import settings
import os
from typing import Any, Optional
from app.utils.date import get_unix_timestamp


class JWTManager:
    def __init__(self, private_key_path=settings.JWT_PRIVATE_KEY_PATH, public_key_path=settings.JWT_PUBLIC_KEY_PATH, algorithm=settings.JWT_ALGORITHM):
        self.algorithm = algorithm
        self.private_key = None
        self.public_key = None

        if private_key_path:
            self.load_private_key(private_key_path)
        if public_key_path:
            self.load_public_key(public_key_path)

    def load_private_key(self, key_path, password=None):
        """加载私钥"""
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Private key file not found: {key_path}")

        with open(key_path, 'rb') as key_file:
            self.private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=password,
                backend=default_backend()
            )

    def load_public_key(self, key_path):
        """加载公钥"""
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Public key file not found: {key_path}")

        with open(key_path, 'rb') as key_file:
            self.public_key = serialization.load_pem_public_key(
                key_file.read(),
                backend=default_backend()
            )

    def create_token(self, payload_data: dict[str, Any]):
        """创建 JWT token"""
        if not self.private_key:
            raise ValueError("Private key not loaded")

        token = jwt.encode(
            payload=payload_data,
            key=self.private_key,
            algorithm=self.algorithm
        )

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

        payload = jwt.decode(
            jwt=token,
            key=self.public_key,
            algorithms=[self.algorithm]
        )
        return payload

    def decode_token_without_verification(self, token):
        """解码 token 但不验证签名（仅用于调试）"""
        return jwt.decode(token, options={"verify_signature": False})


# 全局单例实例
_jwt_manager: Optional[JWTManager] = None


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

    在应用启动时调用，提前加载密钥文件

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
