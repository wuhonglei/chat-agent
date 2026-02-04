"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.conversation import ConversationDb
from app.models.message import MessageDb
from app.models.user import UserDb
from app.models.user_context_db import UserContextDb
from app.models.user_profile_db import UserProfileDb

__all__ = [
    "UserDb",
    "ConversationDb",
    "MessageDb",
    "UserProfileDb",
    "UserContextDb",
]
