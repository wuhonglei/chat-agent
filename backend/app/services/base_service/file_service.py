"""文件服务"""

from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.utils.avatar import (
    assert_allowed_upload_extension,
    avatar_storage_path,
)
from app.utils.common import gen_uuid
from app.utils.file import get_file_extension, write_file_async
from app.utils.logger import logger


class FileService:
    """文件服务"""

    @staticmethod
    async def upload_avatar(file: UploadFile) -> str:
        """
        上传头像到本地 data/avatars/

        Args:
            file: 上传的文件对象

        Returns:
            GET 访问路径 /api/avatars/{filename}
        """
        file_ext = get_file_extension(file.filename or "")
        assert_allowed_upload_extension(file_ext)

        filename = f"{gen_uuid()}{file_ext}"
        avatar_dir = Path(settings.storage.avatar_dir)
        avatar_dir.mkdir(parents=True, exist_ok=True)
        dest = avatar_dir / filename

        logger.info(
            "Avatar upload started",
            filename=file.filename,
            content_type=file.content_type,
            file_ext=file_ext,
            dest=str(dest),
        )

        await write_file_async(str(dest), file)
        storage_path = avatar_storage_path(filename)
        logger.info("Avatar saved locally", storage_path=storage_path)
        return storage_path
