from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag


def strip_dom_attributes_keep_structure(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if isinstance(tag, Tag):
            tag.attrs = {}
    return str(soup)


def html_to_text_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="", strip=False)


def main() -> None:
    here = Path(__file__).resolve().parent
    html_path = here / "raw.html"

    html = html_path.read_text(encoding="utf-8")

    # 默认按“仅保留 textContent（纯文本）”输出
    text_only = html_to_text_content(html)
    (here / "text.txt").write_text(text_only, encoding="utf-8")

    # 同时生成一份“保留标签结构但移除全部属性”的 HTML，便于对比验证
    stripped_html = strip_dom_attributes_keep_structure(html)
    (here / "stripped.html").write_text(stripped_html, encoding="utf-8")


if __name__ == "__main__":
    main()
