"""用户头像 API（本地上传与读取）。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.response import ApiResponse
from app.services.base_service.file_service import FileService
from app.utils.auth_deps import require_auth
from app.utils.avatar import (
    InvalidAvatarError,
    avatar_local_path,
    media_type_for_avatar,
)

router = APIRouter()


@router.post("/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """上传头像（需登录）；保存至 data/avatars，返回 /api/avatars/{filename}。"""
    try:
        storage_path = await FileService.upload_avatar(file)
    except InvalidAvatarError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApiResponse.success(data=storage_path, msg="头像上传成功")


@router.get("/{filename}")
async def get_avatar(filename: str) -> FileResponse:
    """读取本地头像文件（无需登录）。"""
    try:
        path = avatar_local_path(filename)
    except InvalidAvatarError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # codeql[py/path-injection]: path 来自 avatar_local_path，已做文件名规范化与目录边界校验。
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    safe_name = path.name
    # codeql[py/path-injection]: 仅读取 avatar_dir 内已通过校验的本地文件。
    return FileResponse(
        path=str(path),
        media_type=media_type_for_avatar(safe_name),
        filename=safe_name,
    )
