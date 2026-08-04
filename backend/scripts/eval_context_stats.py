"""统计 conversation 首条问答的 context 覆盖情况。

用法:
    DATABASE__HOST=134.175.182.235 uv run python scripts/eval_context_stats.py
"""

from sqlalchemy import text

from app.core.db import get_db

TARGET_USER = "c7d40833-6b26-4696-828f-a94b9de5b47d"

# 需要提取 context 的工具类型
CONTEXT_TOOLS = {
    "tavily_web_search", "tavily_web_pages_extract",
    "code_execute_code",
    "zread_read_file", "zread_get_repo_structure", "zread_search_doc",
    "file_present_files",
}


def analyze():
    session = next(get_db())

    # 1. 获取目标用户的所有 conversation
    result = session.execute(
        text("""
            SELECT c.id, c.created_at
            FROM conversations c
            WHERE c.user_id = :uid
            ORDER BY created_at DESC
        """),
        {"uid": TARGET_USER},
    )
    conversations = [(r[0], r[1]) for r in result]
    print(f"总 conversation 数: {len(conversations)}\n")

    total = 0
    has_tool_ctx = 0
    has_attachment_ctx = 0
    has_any_ctx = 0
    no_ctx = 0

    tool_tool_names: dict[str, int] = {}
    attachment_types: dict[str, int] = {}

    for conv_id, _ in conversations:
        result = session.execute(
            text("""
                SELECT role, content_blocks, created_at, status
                FROM messages
                WHERE conversation_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": conv_id},
        )
        messages = list(result)
        if not messages:
            continue

        # 提取 user query
        query = None
        for role, blocks, _, _ in messages:
            if role != "user" or not blocks:
                continue
            for block in blocks:
                if block.get("type") == "text":
                    query = block.get("text", "").strip()
                    break
            if query:
                break

        if not query:
            continue

        # 提取 assistant answer
        answer = None
        for role, blocks, _, _ in reversed(messages):
            if role != "assistant" or not blocks:
                continue
            for block in reversed(blocks):
                if block.get("type") == "text":
                    txt = block.get("text", "").strip()
                    if txt and len(txt) > 10:
                        answer = txt
                        break
            if answer:
                break

        if not answer:
            continue

        total += 1

        # 检查 tool_result context
        found_tool = False
        for role, blocks, _, _ in messages:
            if role != "assistant" or not blocks:
                continue
            for block in blocks:
                if block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if content:
                        found_tool = True
                        # 统计工具名称（从 tool_use block 推断）
                        tool_name = block.get("name", "unknown")
                        tool_tool_names[tool_name] = tool_tool_names.get(tool_name, 0) + 1

        # 检查用户附件 context
        found_attachment = False
        for role, blocks, _, _ in messages:
            if role != "user" or not blocks:
                continue
            for block in blocks:
                btype = block.get("type", "")
                if btype not in ("text", "tool_result", ""):
                    found_attachment = True
                    attachment_types[btype] = attachment_types.get(btype, 0) + 1
            if found_attachment:
                break

        if found_tool:
            has_tool_ctx += 1
        if found_attachment:
            has_attachment_ctx += 1
        if found_tool or found_attachment:
            has_any_ctx += 1
        else:
            no_ctx += 1

    # 输出统计
    print("=" * 50)
    print(f"有效 conversation（有 query+answer）: {total}")
    print("=" * 50)
    print(f"有 context 总计:   {has_any_ctx}  ({has_any_ctx/total*100:.1f}%)")
    print(f"  - 有 tool context:      {has_tool_ctx}  ({has_tool_ctx/total*100:.1f}%)")
    print(f"  - 有 attachment context: {has_attachment_ctx}  ({has_attachment_ctx/total*100:.1f}%)")
    print(f"无 context:        {no_ctx}  ({no_ctx/total*100:.1f}%)")

    if tool_tool_names:
        print(f"\n--- tool_result 工具分布 ---")
        for name, count in sorted(tool_tool_names.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}")

    if attachment_types:
        print(f"\n--- 附件类型分布 ---")
        for name, count in sorted(attachment_types.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}")


if __name__ == "__main__":
    analyze()
