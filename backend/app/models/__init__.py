"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.db import User, Conversation, Message  # noqa: F401

__all__ = ["User", "Conversation", "Message"]
