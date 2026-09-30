"""Image-part virtual-path labels in build_user_content_for_llm."""

from __future__ import annotations

from typing import Any, cast

from app.schemas.chat import ImageBlock
from app.utils.multimodal import build_user_content_for_llm
from app.vfs.config import vfs_config


def _image(
    block_id: str,
    *,
    storage_key: str | None = None,
    url: str = "data:image/png;base64,AAAA",
) -> ImageBlock:
    return ImageBlock(
        id=block_id,
        url=url,
        mime="image/png",
        size=10,
        storage_key=storage_key,
    )


def _parts(blocks: list[ImageBlock], leading_text: str | None = None) -> list[dict[str, Any]]:
    result = build_user_content_for_llm(
        cast("list[Any]", blocks), leading_text=leading_text
    )
    assert isinstance(result, list)
    return cast("list[dict[str, Any]]", result)


def test_multi_image_labels_with_virtual_paths() -> None:
    parts = _parts(
        [
            _image("i1", storage_key="cid/a.png"),
            _image("i2", storage_key="cid/b.png"),
        ],
        leading_text="请分析这两张图",
    )
    assert [p["type"] for p in parts] == [
        "text",
        "text",
        "image_url",
        "text",
        "image_url",
    ]
    prefix = vfs_config.uploads_prefix
    assert parts[0]["text"] == "请分析这两张图"
    assert parts[1]["text"] == f"[图片 1/2：{prefix}a.png]"
    assert parts[3]["text"] == f"[图片 2/2：{prefix}b.png]"
    assert parts[2]["image_url"]["url"].startswith("data:image/")
    assert parts[4]["image_url"]["url"].startswith("data:image/")


def test_single_image_labeled_with_path() -> None:
    parts = _parts([_image("i1", storage_key="cid/only.png")])
    assert [p["type"] for p in parts] == ["text", "image_url"]
    assert parts[0]["text"] == f"[图片 1/1：{vfs_config.uploads_prefix}only.png]"


def test_label_falls_back_to_preview_url_storage_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.utils.multimodal._build_image_data_url",
        lambda _block: "data:image/png;base64,AAAA",
    )
    block = _image("i1", url="/api/file/preview/user1/cid%2Fa.png")
    parts = _parts([block])
    assert [p["type"] for p in parts] == ["text", "image_url"]
    assert parts[0]["text"] == f"[图片 1/1：{vfs_config.uploads_prefix}a.png]"


def test_multi_image_without_paths_keeps_index_labels() -> None:
    parts = _parts([_image("i1"), _image("i2")])
    labels = [p["text"] for p in parts if p["type"] == "text"]
    assert labels == ["[图片 1/2]", "[图片 2/2]"]


def test_single_image_without_path_unlabeled() -> None:
    parts = _parts([_image("i1")])
    assert [p["type"] for p in parts] == ["image_url"]


def test_text_only_message_still_returns_string() -> None:
    content = build_user_content_for_llm(
        cast("list[Any]", []), leading_text="hello", include_text_blocks=True
    )
    assert content == "hello"


def test_labels_are_deterministic_across_rebuilds() -> None:
    blocks = [
        _image("i1", storage_key="cid/a.png"),
        _image("i2", storage_key="cid/b.png"),
    ]
    assert _parts(blocks, leading_text="q") == _parts(blocks, leading_text="q")
