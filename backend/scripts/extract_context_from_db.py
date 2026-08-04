"""从数据库 messages 表补充 context（针对 Langfuse API 无法获取 observations 的 trace）。

用法:
    uv run python scripts/extract_context_from_db.py
"""

import json
import subprocess
from pathlib import Path

from sqlmodel import select

from app.core.db import get_db
from app.models.message_db import MessageDb

EVAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples.json"
)
ANNOTATED_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples_annotated.json"
)
API_BASE = "https://chat.wuhonglei.cn"

# 需要提取 context 的工具类型
CONTEXT_TOOLS = {
    "tavily_web_search",
    "tavily_web_pages_extract",
    "code_execute_code",
    "zread_read_file",
    "zread_get_repo_structure",
    "zread_search_doc",
    "file_present_files",
}


def fetch_derived_markdown(url: str) -> str | None:
    """通过 API 获取附件派生的 markdown 内容。"""
    full_url = f"{API_BASE}{url}"
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "10", "--max-time", "30", full_url],
            capture_output=True,
            text=True,
            timeout=35,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    return None


def extract_attachment_context(blocks: list[dict]) -> str | None:
    """从用户消息的 content_blocks 中提取附件 context。"""
    parts = []
    for block in blocks:
        btype = block.get("type", "")
        if btype == "text" or btype == "tool_result":
            continue
        name = block.get("name", "")
        size = block.get("size", 0)
        mime = block.get("mime", "")
        md = block.get("markdown")

        desc_lines = [
            f"文件名: {name}",
            f"类型: {btype} ({mime})",
            f"大小: {size} bytes",
        ]
        if md:
            md_name = md.get("name", "")
            md_size = md.get("size", 0)
            md_tokens = md.get("token_size")
            md_lines = md.get("lines_count")
            desc_lines.append(
                f"派生 Markdown: {md_name} ({md_size} bytes"
                + (f", {md_tokens} tokens" if md_tokens else "")
                + (f", {md_lines} lines" if md_lines else "")
                + ")"
            )
        parts.append("\n".join(desc_lines))

        if md and md.get("url"):
            content = fetch_derived_markdown(md["url"])
            if content:
                parts.append(content)

    if not parts:
        return None
    return "<attachment>\n" + "\n\n".join(parts) + "\n</attachment>"


def extract_context_from_messages(conversation_id: str, session) -> str | None:
    """从 messages 表的 content_blocks 中提取工具返回内容。"""
    stmt = select(MessageDb).where(MessageDb.conversation_id == conversation_id)
    msgs = session.exec(stmt).all()

    context_parts = []
    for m in msgs:
        if not m.content_blocks:
            continue
        for block in m.content_blocks:
            if block.get("type") != "tool_result":
                continue
            content = block.get("content", "")
            if not content:
                continue
            # 截断过长的输出
            max_len = 3000
            truncated = content[:max_len] + ("..." if len(content) > max_len else "")
            context_parts.append(f"<tool>\n{truncated}\n</tool>")

    # 提取用户附件 context（pdf/xlsx/docx 等派生 markdown）
    for m in msgs:
        if m.role != "user" or not m.content_blocks:
            continue
        att_ctx = extract_attachment_context(m.content_blocks)
        if att_ctx:
            context_parts.append(att_ctx)
            break

    if not context_parts:
        return None
    return "\n\n".join(context_parts)


def main():
    session = next(get_db())

    eval_items = json.loads(EVAL_PATH.read_text())
    annotated_items = (
        json.loads(ANNOTATED_PATH.read_text()) if ANNOTATED_PATH.exists() else []
    )

    no_context = [item for item in eval_items if not item.get("context")]
    print(f"Total: {len(eval_items)}, No context: {len(no_context)}")

    context_map = {}
    extracted = 0
    skipped = 0

    for i, item in enumerate(no_context):
        sid = item.get("session_id")
        if not sid:
            skipped += 1
            continue

        context = extract_context_from_messages(sid, session)
        if context:
            context_map[item["trace_id"]] = context
            extracted += 1
            print(
                f"  [{i + 1}/{len(no_context)}] {item['trace_id'][:12]}... extracted ({len(context)} chars)"
            )
        else:
            skipped += 1

    print(f"\nExtracted: {extracted}, Skipped: {skipped}")

    # 更新两个文件
    updated_eval = 0
    for item in eval_items:
        if not item.get("context") and item["trace_id"] in context_map:
            item["context"] = context_map[item["trace_id"]]
            updated_eval += 1
    EVAL_PATH.write_text(json.dumps(eval_items, ensure_ascii=False, indent=2))
    print(f"Updated eval_samples.json: {updated_eval} items")

    if annotated_items:
        updated_annotated = 0
        for item in annotated_items:
            if not item.get("context") and item["trace_id"] in context_map:
                item["context"] = context_map[item["trace_id"]]
                updated_annotated += 1
        ANNOTATED_PATH.write_text(
            json.dumps(annotated_items, ensure_ascii=False, indent=2)
        )
        print(f"Updated eval_samples_annotated.json: {updated_annotated} items")


if __name__ == "__main__":
    main()
