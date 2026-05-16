"""对话附件上传与处理服务。"""

from app.services.chat_upload.attachment import (
    MARKDOWN_CONTENT_TYPE,
    MAX_CHAT_ATTACHMENT_BYTES,
    PDF_CONTENT_TYPE,
    build_attachment_preview_url,
    get_user_upload_dir,
    media_type_for_preview,
    sanitize_upload_display_name,
    save_chat_attachment,
    user_upload_file_path,
)
from app.services.chat_upload.image import save_chat_image
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    index_uploaded_text_chunks,
)
from app.services.chat_upload.markdown import save_chat_markdown
from app.services.chat_upload.pdf import save_chat_pdf
from app.services.chat_upload.pdf_markdown_converter import (
    PdfMarkdownConversionError,
    PdfMarkdownConverter,
)

__all__ = [
    "MARKDOWN_CONTENT_TYPE",
    "MAX_CHAT_ATTACHMENT_BYTES",
    "PDF_CONTENT_TYPE",
    "build_attachment_preview_url",
    "get_user_upload_dir",
    "media_type_for_preview",
    "sanitize_upload_display_name",
    "save_chat_attachment",
    "user_upload_file_path",
    "save_chat_image",
    "save_chat_markdown",
    "save_chat_pdf",
    "KbFileChunkIndexingError",
    "index_uploaded_text_chunks",
    "PdfMarkdownConversionError",
    "PdfMarkdownConverter",
]
