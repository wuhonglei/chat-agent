"""文件管理 API"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.db import get_db
from app.schemas.auth import AuthTokenPayload
from app.schemas.chat import AttachmentBlock
from app.schemas.response import ApiResponse
from app.services.base_service.file_service import FileService
from app.services.chat_upload.attachment import (
    media_type_for_preview,
    save_chat_attachment,
    user_upload_file_path,
)
from app.utils.auth_deps import get_auth_token_info, require_auth

router = APIRouter()


@router.post("/upload")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[AttachmentBlock]:
    """上传聊天附件（需登录）；保存至 shared/uploads 并挂载到会话。"""
    block = await save_chat_attachment(
        user_id=auth_info.user_id,
        file=file,
        conversation_id=conversation_id,
        db=db,
    )
    return ApiResponse.success(data=block, msg="上传成功")


@router.get("/preview/{user_id}/{storage_key:path}")
async def preview_chat_attachment(user_id: str, storage_key: str) -> FileResponse:
    """预览已上传附件（无需登录）；依赖路径不可猜测性。"""
    path: Path = user_upload_file_path(user_id, storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=str(path),
        media_type=media_type_for_preview(storage_key),
        filename=Path(storage_key).name,
    )


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
