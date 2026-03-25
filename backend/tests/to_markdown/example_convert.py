"""
MarkItDown 转换示例：将本目录下的样例文件转为 Markdown 文本。

与业务代码中用法一致：``MarkItDown().convert(path)``，读取 ``result.text_content``。

运行（在 backend 根目录）::

    uv run python tests/to_markdown/example_convert.py
    uv run python tests/to_markdown/example_convert.py --file plain
    uv run python tests/to_markdown/example_convert.py --file html

转换结果写入 ``tests/to_markdown/output/<源文件主名>.md``。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from markitdown import MarkItDown

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
SAMPLES = {
    "plain": HERE / "data/sample_plain.txt",
    "html": HERE / "data/sample_structured.html",
}


def convert_path(path: Path) -> str:
    result = MarkItDown().convert(str(path))
    return (result.text_content or "").rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="MarkItDown 样例转换")
    parser.add_argument(
        "--file",
        choices=("plain", "html", "all"),
        default="all",
        help="plain=纯文本 txt；html=结构化网页；all=两者都跑",
    )
    args = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)

    keys = list(SAMPLES) if args.file == "all" else [args.file]
    for key in keys:
        path = SAMPLES[key]
        if not path.is_file():
            raise SystemExit(f"missing sample: {path}")
        out_path = OUTPUT / f"{path.stem}.md"
        text = convert_path(path)
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {out_path} ({key}, source={path.name})")


if __name__ == "__main__":
    main()
