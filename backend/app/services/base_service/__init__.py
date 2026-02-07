"""基础设施服务

此目录包含不依赖于数据库的基础设施服务，如对象存储、文件服务、Embedding 等。
这些服务通常封装了外部系统或基础设施的调用。
"""

from app.services.base_service.embedding_service import EmbeddingService
from app.services.base_service.file_service import FileService
from app.services.base_service.object_storage_service import ObjectStorageService

__all__ = [
    "EmbeddingService",
    "FileService",
    "ObjectStorageService",
]
