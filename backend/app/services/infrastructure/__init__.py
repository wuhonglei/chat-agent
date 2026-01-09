"""基础设施服务

此目录包含不依赖于数据库的基础设施服务，如对象存储、文件服务等。
这些服务通常封装了外部系统或基础设施的调用。
"""

from app.services.infrastructure.file_service import FileService
from app.services.infrastructure.object_storage_service import ObjectStorageService

__all__ = [
    "FileService",
    "ObjectStorageService",
]
