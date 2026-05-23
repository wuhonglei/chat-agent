"""应用数据模型"""

# 导入数据库模型以自动注册表
from app.models.conversation_contexts_db import ConversationContextDb
from app.models.conversation_db import ConversationDb
from app.models.kb_file_chunk_embedding_db import KbFileChunkEmbeddingDb
from app.models.message_db import MessageDb
from app.models.user import UserDb

__all__ = [
    "UserDb",
    "ConversationDb",
    "MessageDb",
    "ConversationContextDb",
    "KbFileChunkEmbeddingDb",
]
