"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.conversation_contexts_db import ConversationContextDb
from app.models.conversation_db import ConversationDb
from app.models.message_db import MessageDb
from app.models.user import UserDb
from app.models.user_profile_item_db import UserProfileItemDb

__all__ = [
    "UserDb",
    "ConversationDb",
    "MessageDb",
    "UserProfileItemDb",
    "ConversationContextDb",
]
