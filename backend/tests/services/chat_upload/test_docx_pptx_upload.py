"""docx / pptx 上传 handler 单元测试（mock MinerU）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.chat_upload import docx as docx_mod
from app.services.chat_upload import pptx as pptx_mod
from app.services.chat_upload.attachment import DOCX_CONTENT_TYPE, PPTX_CONTENT_TYPE


def _fake_upload(*, filename: str, content_type: str, data: bytes) -> MagicMock:
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type
    upload.read = AsyncMock(return_value=data)
    return upload


@pytest.mark.asyncio
async def test_save_chat_docx_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "user-1"
    conversation_id = "11111111-1111-1111-1111-111111111111"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setattr(docx_mod, "ensure_conversation_owned", lambda *a, **k: None)
    monkeypatch.setattr(
        docx_mod, "get_conversation_upload_dir", lambda *a, **k: upload_dir
    )
    monkeypatch.setattr(
        docx_mod, "allocate_unique_display_name", lambda *a, **k: "report.docx"
    )

    async def fake_convert(self, file_path, *, md_path, images_dir):  # noqa: ANN001
        md_path.parent.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text("# hello\n", encoding="utf-8")
        return "# hello\n"

    monkeypatch.setattr(
        docx_mod.MinerUMarkdownConverter,
        "convert_to_markdown",
        fake_convert,
    )
    monkeypatch.setattr(
        docx_mod,
        "index_uploaded_text_chunks",
        AsyncMock(return_value=None),
    )

    file = _fake_upload(
        filename="report.docx",
        content_type=DOCX_CONTENT_TYPE,
        data=b"PK\x03\x04" + b"x" * 20,
    )
    block = await docx_mod.save_chat_docx(
        user_id=user_id,
        file=file,
        conversation_id=conversation_id,
        db=None,
    )
    assert block.type == "docx"
    assert block.name == "report.docx"
    assert block.markdown is not None
    assert block.markdown.derived_kind == "docx_to_markdown"
    assert (upload_dir / "report.docx").is_file()
    assert (upload_dir / "derived" / "report.md").is_file()


@pytest.mark.asyncio
async def test_save_chat_docx_rejects_bad_magic() -> None:
    file = _fake_upload(
        filename="a.docx",
        content_type=DOCX_CONTENT_TYPE,
        data=b"not-a-zip",
    )
    with pytest.raises(HTTPException) as exc:
        await docx_mod.save_chat_docx(
            user_id="u",
            file=file,
            conversation_id="11111111-1111-1111-1111-111111111111",
            db=None,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_chat_pptx_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "user-1"
    conversation_id = "22222222-2222-2222-2222-222222222222"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setattr(pptx_mod, "ensure_conversation_owned", lambda *a, **k: None)
    monkeypatch.setattr(
        pptx_mod, "get_conversation_upload_dir", lambda *a, **k: upload_dir
    )
    monkeypatch.setattr(
        pptx_mod, "allocate_unique_display_name", lambda *a, **k: "deck.pptx"
    )

    async def fake_convert(self, file_path, *, md_path, images_dir):  # noqa: ANN001
        md_path.parent.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text("# slides\n", encoding="utf-8")
        return "# slides\n"

    monkeypatch.setattr(
        pptx_mod.MinerUMarkdownConverter,
        "convert_to_markdown",
        fake_convert,
    )
    monkeypatch.setattr(
        pptx_mod,
        "index_uploaded_text_chunks",
        AsyncMock(return_value=None),
    )

    file = _fake_upload(
        filename="deck.pptx",
        content_type=PPTX_CONTENT_TYPE,
        data=b"PK\x03\x04" + b"y" * 20,
    )
    block = await pptx_mod.save_chat_pptx(
        user_id=user_id,
        file=file,
        conversation_id=conversation_id,
        db=None,
    )
    assert block.type == "pptx"
    assert block.markdown is not None
    assert block.markdown.derived_kind == "pptx_to_markdown"
    assert (upload_dir / "deck.pptx").is_file()


@pytest.mark.asyncio
async def test_save_chat_pptx_rejects_wrong_extension() -> None:
    file = _fake_upload(
        filename="a.txt",
        content_type="text/plain",
        data=b"PK\x03\x04xxxx",
    )
    with pytest.raises(HTTPException) as exc:
        await pptx_mod.save_chat_pptx(
            user_id="u",
            file=file,
            conversation_id="22222222-2222-2222-2222-222222222222",
            db=None,
        )
    assert exc.value.status_code == 400
