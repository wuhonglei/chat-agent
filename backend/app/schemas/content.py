"""多模态内容 Schema（Content Parts）"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileObject(BaseModel):
    conversation_id: str = Field(..., description="对话 ID")
    filename: str = Field(..., description="文件名")
    stored_filename: str = Field(..., description="存储文件名")
    mime_type: str = Field(..., description="文件 MIME 类型")
    virtual_path: str = Field(..., description="虚拟路径")
    artifact_url: str = Field(..., description="文件 URL")
    markdown_file: str | None = Field(None, description="Markdown 文件")
    markdown_virtual_path: str | None = Field(None, description="Markdown 虚拟路径")
    markdown_artifact_url: str | None = Field(None, description="Markdown 文件 URL")


class TextContentPart(BaseModel):
    type: Literal["text"]
    text: str


class ImageContentPart(BaseModel):
    type: Literal["image"]
    image: FileObject


class FileContentPart(BaseModel):
    type: Literal["file"]
    file: FileObject


ContentPart = TextContentPart | ImageContentPart | FileContentPart
