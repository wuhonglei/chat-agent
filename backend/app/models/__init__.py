"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.user import UserDb
from app.models.conversation import ConversationDb
from app.models.message import MessageDb

__all__ = ["UserDb", "ConversationDb", "MessageDb"]
