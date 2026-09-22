"""trace_media：图片引用解析单元测试。"""

from __future__ import annotations

from app.services.eval.trace_media import (
    _parse_media_marker,
    resolve_image_ref,
    resolve_image_refs,
)

MARKER = (
    "@@@langfuseMedia:type=image/jpeg"
    "|id=QFKfQFDG8qvj6r03Ci0MDe|source=base64_data_uri@@@"
)


def test_parse_media_marker() -> None:
    parsed = _parse_media_marker(MARKER)
    assert parsed == ("QFKfQFDG8qvj6r03Ci0MDe", "image/jpeg")
    assert _parse_media_marker("data:image/png;base64,xxx") is None
    assert _parse_media_marker("@@@langfuseMedia:type=image/png|source=x@@@") is None


def test_resolve_image_ref_passthrough_data_uri() -> None:
    data_uri = "data:image/png;base64,iVBORw0KGgo="
    assert resolve_image_ref(data_uri) == data_uri


def test_resolve_image_ref_passthrough_http_url() -> None:
    url = "https://example.com/a.png"
    assert resolve_image_ref(url) == url


def test_resolve_image_ref_rejects_unknown() -> None:
    assert resolve_image_ref("not-an-image") is None
    assert resolve_image_ref("  ") is None


def test_resolve_image_refs_drops_failures(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _fake_one(ref: str) -> str | None:
        return "data:image/jpeg;base64,OK" if ref == "good" else None

    monkeypatch.setattr(
        "app.services.eval.trace_media.resolve_image_ref",
        _fake_one,
    )
    assert resolve_image_refs(["good", "bad", "good"]) == [
        "data:image/jpeg;base64,OK",
        "data:image/jpeg;base64,OK",
    ]
