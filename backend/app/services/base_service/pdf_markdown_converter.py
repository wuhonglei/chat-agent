"""PDF 转 Markdown 转换器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import httpx
import pymupdf
from markitdown import MarkItDown

try:
    from mineru_kie_sdk import MineruKIEClient
except Exception:  # pragma: no cover - 依赖缺失时仅在运行时兜底
    MineruKIEClient = None

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

    def convert_text_pdf_with_markitdown(self, pdf_path: Path) -> str:
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

    def convert_scan_pdf_with_mineru_kie_sdk(self, pdf_path: Path) -> str:
        """扫描型 PDF 使用 MinerU KIE SDK 转换。"""
        cfg = self._config
        if not cfg.mineru_kie_pipeline_id:
            raise PdfMarkdownConversionError("未配置 MinerU KIE Pipeline ID")
        if MineruKIEClient is None:
            raise PdfMarkdownConversionError("mineru-kie-sdk 未安装或不可用")

        try:
            kie_client_cls = cast(Any, MineruKIEClient)
            client = kie_client_cls(
                base_url=cfg.mineru_kie_base_url,
                pipeline_id=cfg.mineru_kie_pipeline_id,
                timeout=max(1, int(cfg.poll_timeout_seconds)),
            )
            file_ids = client.upload_file(str(pdf_path))
            results = client.get_result(
                file_ids=file_ids,
                timeout=max(1, int(cfg.poll_timeout_seconds)),
                poll_interval=max(1, int(cfg.poll_interval_seconds)),
            )
            markdown = self._extract_markdown(results)
        except PdfMarkdownConversionError:
            raise
        except Exception as exc:
            raise PdfMarkdownConversionError("MinerU KIE SDK 转换失败") from exc

        logger.info(
            "MinerU KIE conversion done",
            pdf_path=str(pdf_path),
            mineru_file_ids=file_ids,
            mineru_pipeline_id=cfg.mineru_kie_pipeline_id,
        )
        return markdown

    def convert_pdf_to_markdown(self, pdf_path: Path) -> str:
        """统一转换入口。"""
        pdf_kind = self.detect_pdf_kind(pdf_path)
        if pdf_kind == "text":
            markdown = self.convert_text_pdf_with_markitdown(pdf_path)
        else:
            markdown = self.convert_scan_pdf_with_mineru_kie_sdk(pdf_path)
        logger.info(
            "PDF markdown conversion done", pdf_path=str(pdf_path), pdf_kind=pdf_kind
        )
        return markdown

    def save_markdown(self, markdown_text: str, md_path: Path) -> None:
        """保存 markdown 到目标路径。"""
        md_path.write_text(markdown_text, encoding="utf-8")

    def _extract_markdown(self, results: Any) -> str:
        markdown = self._extract_markdown_value(results)
        if not markdown.strip():
            raise PdfMarkdownConversionError("MinerU KIE 未返回有效 Markdown 内容")
        return markdown

    def _extract_markdown_value(self, obj: Any) -> str:
        if isinstance(obj, str):
            return ""

        if isinstance(obj, dict):
            for key in ("markdown", "md", "md_content"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    return value

            for key in ("markdown_url", "md_url"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    return self._download_markdown(value)

            for value in obj.values():
                nested = self._extract_markdown_value(value)
                if nested.strip():
                    return nested
            return ""

        if isinstance(obj, list):
            for item in obj:
                nested = self._extract_markdown_value(item)
                if nested.strip():
                    return nested
            return ""

        return ""

    def _download_markdown(self, url: str) -> str:
        try:
            with httpx.Client(
                timeout=max(1.0, self._config.poll_timeout_seconds)
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as exc:
            raise PdfMarkdownConversionError("下载 MinerU Markdown 结果失败") from exc
