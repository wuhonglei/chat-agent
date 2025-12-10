"""
文件管理
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.config import settings
from app.models.response import ApiResponse
from app.services.object_storage_service import ObjectStorageService
from app.utils.auth_deps import require_auth
from app.utils.decorators import handle_api_exceptions
from app.utils.file import TempFileManager, get_file_extension, write_file_async
from app.utils.logger import logger

router = APIRouter()


@router.post("/upload_avatar")
@handle_api_exceptions(
    operation_name="上传头像",
    default_message="头像上传失败"
)
async def upload_avatar(
    file: UploadFile = File(...),
    _auth: None = Depends(require_auth),
):
    """
    上传头像

    从 multipart/form-data 请求中解析文件对象并上传到 COS

    Args:
        file: FastAPI 自动解析的 UploadFile 对象

    Returns:
        上传后的文件 URL
    """
    file_ext = get_file_extension(file.filename)
    avatar_dir = Path(settings.storage.avatar_dir)

    file_size = file.size if hasattr(file, 'size') else None
    logger.info(
        "Avatar upload started",
        filename=file.filename,
        content_type=file.content_type,
        file_size=file_size,
        file_ext=file_ext,
    )

    # 使用上下文管理器自动管理临时文件的创建和删除
    async with TempFileManager(avatar_dir, file_ext) as temp_file:
        # 写入文件
        await write_file_async(str(temp_file.path), file)
        logger.info(
            f"文件已保存到临时文件: "
            f"temp_file_path={str(temp_file.path)}",
        )

        # 生成 COS 路径（使用文件名，不包含目录）
        new_file_name = temp_file.path.name
        cos_path = f"avatars/{new_file_name}"

        # 上传到 COS
        with ObjectStorageService() as storage:
            new_file_url = await storage.upload_file(
                local_path=str(temp_file.path),
                cos_path=cos_path
            )
            logger.info(
                f"文件已上传到 COS: "
                f"cos_path={cos_path}, file_url={new_file_url}",
            )

        return ApiResponse.success(data=new_file_url)
