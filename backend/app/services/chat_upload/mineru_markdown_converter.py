"""MinerU SaaS: PDF/Excel -> Markdown 转换（通过 mineru.net 云端 API）。"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import zipfile
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.config import MinerUConfig
from app.utils.logger import logger

# content_list_v2.json 中 sub_type -> 中文描述
_SUB_TYPE_MAP = {
    "seal": "公章",
    "chart": "图表",
    "table": "表格图片",
    "figure": "插图",
    "equation": "公式",
    "code": "代码截图",
    "signature": "签名",
}

_IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})


class MinerUMarkdownConversionError(RuntimeError):
    """MinerU 转 Markdown 失败。"""


class MinerUMarkdownConverter:
    """通过 MinerU SaaS 批量解析接口将文档转为 Markdown。"""

    def __init__(self, config: MinerUConfig | None = None) -> None:
        self._config = config or settings.mineru

    async def convert_to_markdown(
        self,
        file_path: Path,
        *,
        md_path: Path,
        images_dir: Path,
    ) -> str:
        """转换入口：写入 md_path，合并图片到 images_dir，返回 markdown 文本。"""
        cfg = self._config
        if not cfg.enabled:
            raise MinerUMarkdownConversionError("MinerU 转换未启用")
        if not cfg.api_key:
            raise MinerUMarkdownConversionError("未配置 MinerU api_key")

        api_url = cfg.api_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=10.0,
            read=max(60.0, cfg.poll_timeout_seconds),
            write=60.0,
            pool=30.0,
        )

        work_dir = Path(mkdtemp(prefix="mineru_"))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                zip_bytes = await self._run_extract_pipeline(
                    client,
                    api_url=api_url,
                    headers=headers,
                    file_path=file_path,
                )

            md_text = self._extract_and_merge(
                zip_bytes,
                work_dir=work_dir,
                md_path=md_path,
                images_dir=images_dir,
                file_stem=file_path.stem,
            )
        except MinerUMarkdownConversionError:
            raise
        except Exception as exc:
            raise MinerUMarkdownConversionError(f"MinerU 转换失败：{exc}") from exc
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        logger.info(
            "MinerU markdown conversion done",
            file_path=str(file_path),
            md_path=str(md_path),
            images_dir=str(images_dir),
        )
        return md_text

    async def _run_extract_pipeline(
        self,
        client: httpx.AsyncClient,
        *,
        api_url: str,
        headers: dict[str, str],
        file_path: Path,
    ) -> bytes:
        cfg = self._config

        batch_resp = await client.post(
            f"{api_url}/api/v4/file-urls/batch",
            headers=headers,
            json={
                "files": [{"name": file_path.name, "data_id": "local"}],
                "model_version": cfg.model_version,
            },
        )
        if batch_resp.status_code != 200:
            raise MinerUMarkdownConversionError(
                f"申请上传 URL 失败: {batch_resp.status_code} {batch_resp.text[:300]}"
            )
        batch_data = batch_resp.json()
        if batch_data.get("code") != 0:
            raise MinerUMarkdownConversionError(
                f"申请上传 URL 失败: {batch_data.get('msg')}"
            )

        data = batch_data.get("data") or {}
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls") or []
        if not batch_id or not file_urls:
            raise MinerUMarkdownConversionError(
                "申请上传 URL 返回缺少 batch_id/file_urls"
            )

        upload_url = file_urls[0]
        file_bytes = await asyncio.to_thread(file_path.read_bytes)
        upload_resp = await client.put(upload_url, content=file_bytes)
        if upload_resp.status_code != 200:
            raise MinerUMarkdownConversionError(
                f"文件上传失败: {upload_resp.status_code}"
            )

        zip_url = await self._poll_batch_result(
            client,
            api_url=api_url,
            headers=headers,
            batch_id=batch_id,
        )

        zip_resp = await client.get(zip_url)
        if zip_resp.status_code != 200:
            raise MinerUMarkdownConversionError(f"下载结果失败: {zip_resp.status_code}")
        return zip_resp.content

    async def _poll_batch_result(
        self,
        client: httpx.AsyncClient,
        *,
        api_url: str,
        headers: dict[str, str],
        batch_id: str,
    ) -> str:
        cfg = self._config
        poll_url = f"{api_url}/api/v4/extract-results/batch/{batch_id}"
        loop = asyncio.get_running_loop()
        deadline = loop.time() + cfg.poll_timeout_seconds

        while loop.time() < deadline:
            await asyncio.sleep(cfg.poll_interval_seconds)
            poll_resp = await client.get(poll_url, headers=headers)
            if poll_resp.status_code != 200:
                raise MinerUMarkdownConversionError(
                    f"查询状态失败: {poll_resp.status_code}"
                )
            poll_data = poll_resp.json()
            if poll_data.get("code") != 0:
                raise MinerUMarkdownConversionError(
                    f"查询状态失败: {poll_data.get('msg')}"
                )

            extract_result = (poll_data.get("data") or {}).get("extract_result") or []
            if not extract_result:
                continue

            all_done = True
            zip_url: str | None = None
            for item in extract_result:
                if not isinstance(item, dict):
                    all_done = False
                    continue
                state = item.get("state", "")
                if state == "done":
                    if not zip_url:
                        candidate = item.get("full_zip_url")
                        if isinstance(candidate, str) and candidate:
                            zip_url = candidate
                elif state == "failed":
                    err_msg = item.get("err_msg", "unknown")
                    raise MinerUMarkdownConversionError(f"解析失败: {err_msg}")
                else:
                    all_done = False

            if all_done:
                if not zip_url:
                    raise MinerUMarkdownConversionError("任务完成但未找到结果 ZIP URL")
                return zip_url

        raise MinerUMarkdownConversionError(
            f"轮询超时（{cfg.poll_timeout_seconds:.0f} 秒）"
        )

    def _extract_and_merge(
        self,
        zip_bytes: bytes,
        *,
        work_dir: Path,
        md_path: Path,
        images_dir: Path,
        file_stem: str,
    ) -> str:
        zip_path = work_dir / "result.zip"
        extract_dir = work_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
            md_text = self._read_markdown_from_zip(zf)
            if md_text:
                md_text = _enrich_image_alt_text(md_text, zf)

        if not md_text.strip():
            raise MinerUMarkdownConversionError("MinerU 未返回有效 Markdown 内容")

        src_images = self._find_images_dir(extract_dir)
        md_text = self._merge_images(
            md_text,
            src_images=src_images,
            images_dir=images_dir,
            file_stem=file_stem,
        )

        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    def _read_markdown_from_zip(self, zf: zipfile.ZipFile) -> str:
        for name in zf.namelist():
            if name.endswith(".md") and not name.endswith("/"):
                return zf.read(name).decode("utf-8")
        return ""

    def _find_images_dir(self, extract_dir: Path) -> Path | None:
        direct = extract_dir / "images"
        if direct.is_dir():
            return direct
        for candidate in extract_dir.rglob("images"):
            if candidate.is_dir():
                return candidate
        return None

    def _merge_images(
        self,
        md_text: str,
        *,
        src_images: Path | None,
        images_dir: Path,
        file_stem: str,
    ) -> str:
        if src_images is None or not src_images.is_dir():
            return md_text

        images_dir.mkdir(parents=True, exist_ok=True)
        renames: dict[str, str] = {}

        for src in sorted(src_images.iterdir()):
            if not src.is_file():
                continue
            if src.suffix.lower() not in _IMAGE_EXTS and src.suffix:
                # 仍允许无扩展名或其它图片后缀落盘
                pass
            dest_name = src.name
            dest = images_dir / dest_name
            if dest.exists():
                dest_name = f"{file_stem}_{src.name}"
                dest = images_dir / dest_name
                # 极端情况下仍冲突则追加计数
                counter = 1
                while dest.exists():
                    dest_name = f"{file_stem}_{counter}_{src.name}"
                    dest = images_dir / dest_name
                    counter += 1
                renames[f"images/{src.name}"] = f"images/{dest_name}"
            shutil.copy2(src, dest)

        if not renames:
            return md_text

        def _replace_path(match: re.Match[str]) -> str:
            alt = match.group(1)
            path = match.group(2)
            new_path = renames.get(path, path)
            return f"![{alt}]({new_path})"

        return _IMAGE_MD_RE.sub(_replace_path, md_text)


def _enrich_image_alt_text(md_text: str, zip_file: zipfile.ZipFile) -> str:
    """从 content_list_v2.json 读取图片 sub_type，替换 markdown 中空 alt text。"""
    clv2_name = None
    for name in zip_file.namelist():
        if name.endswith("_content_list_v2.json"):
            clv2_name = name
            break
    if not clv2_name:
        return md_text

    try:
        clv2: Any = json.loads(zip_file.read(clv2_name))
    except Exception:
        return md_text

    image_meta: dict[str, str] = {}
    if not isinstance(clv2, list):
        return md_text

    for page in clv2:
        if not isinstance(page, list):
            continue
        for block in page:
            if not isinstance(block, dict) or block.get("type") != "image":
                continue
            content = block.get("content") or {}
            if not isinstance(content, dict):
                continue
            image_source = content.get("image_source") or {}
            if not isinstance(image_source, dict):
                continue
            img_path = image_source.get("path", "")
            sub_type = block.get("sub_type", "")
            if (
                isinstance(img_path, str)
                and img_path
                and isinstance(sub_type, str)
                and sub_type
            ):
                image_meta[img_path] = _SUB_TYPE_MAP.get(sub_type, sub_type)

    if not image_meta:
        return md_text

    def _replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        path = match.group(2)
        if alt:
            return match.group(0)
        desc = image_meta.get(path, "")
        if desc:
            return f"![{desc}]({path})"
        return match.group(0)

    return _IMAGE_MD_RE.sub(_replace, md_text)
