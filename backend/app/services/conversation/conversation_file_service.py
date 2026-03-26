"""对话文件（上传/预览）服务"""

from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from markitdown import MarkItDown
from sqlmodel import Session

from app.schemas.content import FileObject
from app.services.conversation.conversation_db import ConversationDbService
from app.utils.file import get_file_extension, write_file_async
from app.utils.logger import logger


class ConversationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ConversationArtifactFile:
    path: Path
    media_type: str
    filename: str


class ConversationFileService:
    """对话文件服务（上传与 artifact 访问）。"""

    def __init__(self, db: Session):
        self._db = db
        self._conversation_db = ConversationDbService(db)

    @staticmethod
    def conversation_uploads_dir(conversation_id: str) -> Path:
        return Path("./data/conversations") / conversation_id / "user-data" / "uploads"

    def _ensure_conversation_exists(self, conversation_id: str) -> None:
        if not self._conversation_db.get_conversation(conversation_id):
            raise ConversationNotFoundError("会话不存在")

    async def upload_conversation_file(
        self,
        conversation_id: str,
        file: UploadFile,
    ) -> FileObject:
        """上传对话相关文件/图片（按 conversation_id 隔离），并在需要时转 Markdown。"""
        self._ensure_conversation_exists(conversation_id)

        filename = file.filename or "file"
        ext = get_file_extension(filename)
        stored_filename = f"{uuid.uuid4().hex}{ext}"

        uploads_dir = self.conversation_uploads_dir(conversation_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        stored_path = uploads_dir / stored_filename

        logger.info(
            "Conversation file upload started",
            conversation_id=conversation_id,
            filename=filename,
            content_type=file.content_type,
            stored_filename=stored_filename,
        )
        await write_file_async(str(stored_path), file)
        file_size = stored_path.stat().st_size

        mime_type = (
            file.content_type
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )
        virtual_path = f"/mnt/user-data/uploads/{stored_filename}"
        artifact_url = f"/api/conversation/{conversation_id}/artifacts/mnt/user-data/uploads/{stored_filename}"

        markdown_file: str | None = None
        markdown_virtual_path: str | None = None
        markdown_artifact_url: str | None = None

        is_pdf = (mime_type == "application/pdf") or (ext.lower() == ".pdf")
        if is_pdf:
            try:
                result = MarkItDown().convert(str(stored_path))
                md_text = (result.text_content or "").rstrip() + "\n"
                if md_text.strip():
                    md_name = f"{Path(stored_filename).stem}.md"
                    md_path = uploads_dir / md_name
                    md_path.write_text(md_text, encoding="utf-8")
                    markdown_file = md_name
                    markdown_virtual_path = f"/mnt/user-data/uploads/{md_name}"
                    markdown_artifact_url = f"/api/conversation/{conversation_id}/artifacts/mnt/user-data/uploads/{md_name}"
            except Exception as e:
                logger.warning(
                    "PDF to markdown conversion failed",
                    conversation_id=conversation_id,
                    stored_filename=stored_filename,
                    error=e,
                )

        return FileObject(
            size=file_size,
            conversation_id=conversation_id,
            filename=filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            virtual_path=virtual_path,
            artifact_url=artifact_url,
            markdown_file=markdown_file,
            markdown_virtual_path=markdown_virtual_path,
            markdown_artifact_url=markdown_artifact_url,
        )

    def get_conversation_artifact_file(
        self,
        conversation_id: str,
        artifact_path: str,
    ) -> ConversationArtifactFile:
        """定位对话上传产物（仅允许 /mnt/user-data/uploads 下的文件）。"""
        self._ensure_conversation_exists(conversation_id)

        normalized = (artifact_path or "").lstrip("/")
        prefix = "mnt/user-data/uploads/"
        if not normalized.startswith(prefix):
            raise HTTPException(status_code=400, detail="不支持的 artifact 路径")

        stored_filename = normalized.removeprefix(prefix)
        if not stored_filename or "/" in stored_filename or "\\" in stored_filename:
            raise HTTPException(status_code=400, detail="非法文件名")

        file_path = self.conversation_uploads_dir(conversation_id) / stored_filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        media_type = (
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        )
        return ConversationArtifactFile(
            path=file_path, media_type=media_type, filename=file_path.name
        )
