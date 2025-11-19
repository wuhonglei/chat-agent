"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.db import UserDb, ConversationDb, MessageDb  # noqa: F401

__all__ = ["UserDb", "ConversationDb", "MessageDb"]
