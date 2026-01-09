"""文件服务"""

from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.services.infrastructure.object_storage_service import ObjectStorageService
from app.utils.file import TempFileManager, get_file_extension, write_file_async
from app.utils.logger import logger


class FileService:
    """文件服务"""

    @staticmethod
    async def upload_avatar(file: UploadFile) -> str:
        """
        上传头像到对象存储

        Args:
            file: 上传的文件对象

        Returns:
            上传后的文件 URL
        """
        file_ext = get_file_extension(file.filename)
        avatar_dir = Path(settings.storage.avatar_dir)

        logger.info(
            "Avatar upload started",
            filename=file.filename,
            content_type=file.content_type,
            file_ext=file_ext,
        )

        # 使用上下文管理器自动管理临时文件的创建和删除
        async with TempFileManager(avatar_dir, file_ext) as temp_file:
            # 写入临时文件
            await write_file_async(str(temp_file.path), file)
            logger.debug("文件已保存到临时文件", temp_file_path=str(temp_file.path))

            # 生成 COS 路径
            cos_path = f"avatars/{temp_file.path.name}"

            # 上传到 COS
            with ObjectStorageService() as storage:
                file_url = await storage.upload_file(
                    local_path=str(temp_file.path),
                    cos_path=cos_path,
                )
                logger.info("文件已上传到 COS", cos_path=cos_path, file_url=file_url)

            return file_url
