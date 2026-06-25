"""Excel 转 Markdown 转换器。"""

from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown

from app.utils.logger import logger


class ExcelMarkdownConversionError(RuntimeError):
    """Excel 转 Markdown 失败。"""


class ExcelMarkdownConverter:
    """使用 MarkItDown 将 Excel (.xlsx) 转为 Markdown。"""

    def convert_excel_to_markdown(self, excel_path: Path) -> str:
        """转换入口：使用 MarkItDown 输出 Markdown 文本。"""
        try:
            result = MarkItDown().convert(str(excel_path))
        except Exception as exc:
            raise ExcelMarkdownConversionError("MarkItDown 转换失败") from exc

        markdown = (getattr(result, "markdown", None) or "").strip()
        if not markdown:
            markdown = (getattr(result, "text_content", None) or "").strip()
        if not markdown:
            raise ExcelMarkdownConversionError("MarkItDown 未返回有效 Markdown 内容")

        logger.info("Excel markdown conversion done", excel_path=str(excel_path))
        return markdown

    def save_markdown(self, markdown_text: str, md_path: Path) -> None:
        """保存 markdown 到目标路径。"""
        md_path.write_text(markdown_text, encoding="utf-8")
