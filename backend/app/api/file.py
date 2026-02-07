"""文件管理 API"""

from fastapi import APIRouter, Depends, File, UploadFile

from app.schemas.response import ApiResponse
from app.services.base_service.file_service import FileService
from app.utils.auth_deps import require_auth

router = APIRouter()


@router.post("/upload_avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """
    上传头像

    从 multipart/form-data 请求中解析文件对象并上传到对象存储

    Args:
        file: FastAPI 自动解析的 UploadFile 对象

    Returns:
        上传后的文件 URL
    """
    file_url = await FileService.upload_avatar(file)
    return ApiResponse.success(data=file_url, msg="头像上传成功")
