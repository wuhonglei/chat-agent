"""PDF 转 Markdown 转换器。"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Literal, cast

import httpx
import pymupdf
from markitdown import MarkItDown

from app.core.config import settings
from app.schemas.config import PdfMarkdownConfig
from app.utils.logger import logger


class PdfMarkdownConversionError(RuntimeError):
    """PDF 转 Markdown 失败。"""


class PdfMarkdownConverter:
    """按 PDF 类型选择不同策略输出 Markdown。"""

    def __init__(self, config: PdfMarkdownConfig | None = None) -> None:
        self._config = config or settings.pdf_markdown

    def detect_pdf_kind(self, pdf_path: Path) -> Literal["text", "scan"]:
        """检测 PDF 是文本型还是扫描型。"""
        pages = 0
        open_pdf = cast(Any, pymupdf.open)
        try:
            with open_pdf(pdf_path) as doc:
                pages = min(self._config.detect_pages, doc.page_count)
                text_length = 0
                for idx in range(pages):
                    text_length += len(doc.load_page(idx).get_text().strip())
        except Exception as exc:
            raise PdfMarkdownConversionError("PDF 类型检测失败") from exc

        pdf_kind: Literal["text", "scan"] = (
            "scan" if text_length < self._config.scan_text_threshold else "text"
        )
        logger.info(
            "PDF kind detected",
            pdf_path=str(pdf_path),
            pdf_kind=pdf_kind,
            text_length=text_length,
            detect_pages=pages,
        )
        return pdf_kind

    def convert_text_pdf(self, pdf_path: Path) -> str:
        """文本型 PDF 使用 MarkItDown 转换。"""
        try:
            result = MarkItDown().convert(str(pdf_path))
        except Exception as exc:
            raise PdfMarkdownConversionError("MarkItDown 转换失败") from exc

        markdown = (getattr(result, "markdown", None) or "").strip()
        if not markdown:
            markdown = (getattr(result, "text_content", None) or "").strip()
        if not markdown:
            raise PdfMarkdownConversionError("MarkItDown 未返回有效 Markdown 内容")
        return markdown

    def convert_scan_pdf(self, pdf_path: Path) -> str:
        """扫描型 PDF 使用 PP-StructureV3 转换。"""
        cfg = self._config
        if not cfg.pp_structure_token:
            raise PdfMarkdownConversionError("未配置 PP-StructureV3 token")

        try:
            pdf_data = pdf_path.read_bytes()
            payload = {
                "file": base64.b64encode(pdf_data).decode("ascii"),
                "fileType": 0,
                "useDocOrientationClassify": False,
                "useDocUnwarping": False,
                "useTextlineOrientation": False,
                "useChartRecognition": False,
            }
            headers = {
                "Authorization": f"token {cfg.pp_structure_token}",
                "Content-Type": "application/json",
            }
            with httpx.Client(
                timeout=max(1.0, cfg.poll_timeout_seconds),
            ) as client:
                response = client.post(
                    cfg.pp_structure_api_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                response_json = response.json()
            markdown = self._extract_pp_structure_markdown(response_json)
        except PdfMarkdownConversionError:
            raise
        except Exception as exc:
            raise PdfMarkdownConversionError("PP-StructureV3 转换失败") from exc

        logger.info(
            "PP-StructureV3 conversion done",
            pdf_path=str(pdf_path),
            pp_structure_api_url=cfg.pp_structure_api_url,
        )
        return markdown

    def convert_pdf_to_markdown(self, pdf_path: Path) -> str:
        """统一转换入口。"""
        pdf_kind = self.detect_pdf_kind(pdf_path)
        if pdf_kind == "text":
            markdown = self.convert_text_pdf(pdf_path)
        else:
            markdown = self.convert_scan_pdf(pdf_path)
        logger.info(
            "PDF markdown conversion done", pdf_path=str(pdf_path), pdf_kind=pdf_kind
        )
        return markdown

    def save_markdown(self, markdown_text: str, md_path: Path) -> None:
        """保存 markdown 到目标路径。"""
        md_path.write_text(markdown_text, encoding="utf-8")

    def _extract_pp_structure_markdown(self, response_json: Any) -> str:
        if not isinstance(response_json, dict):
            raise PdfMarkdownConversionError("PP-StructureV3 返回格式无效")

        result = response_json.get("result")
        if not isinstance(result, dict):
            raise PdfMarkdownConversionError("PP-StructureV3 返回缺少 result 字段")

        layout_results = result.get("layoutParsingResults")
        if not isinstance(layout_results, list) or not layout_results:
            raise PdfMarkdownConversionError(
                "PP-StructureV3 返回缺少 layoutParsingResults 字段"
            )

        markdown_parts: list[str] = []
        for item in layout_results:
            if not isinstance(item, dict):
                continue
            markdown_obj = item.get("markdown")
            if not isinstance(markdown_obj, dict):
                continue
            text = markdown_obj.get("text")
            if isinstance(text, str) and text.strip():
                markdown_parts.append(text.strip())

        markdown = "\n\n".join(markdown_parts).strip()
        if not markdown:
            raise PdfMarkdownConversionError("PP-StructureV3 未返回有效 Markdown 文本")
        return markdown
