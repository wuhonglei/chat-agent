#!/usr/bin/env python3
"""
从数据库获取原始 content_blocks 并进行精确分类
"""

import json
import sys
from collections import Counter, defaultdict
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


def fetch_qa_pairs_with_content_blocks(conn, limit: int = 2000):
    """获取问答对及其 content_blocks"""
    query = """
    SELECT
        m_assistant.id as assistant_message_id,
        m_assistant.content_blocks,
        m_assistant.message_metadata,
        m_user.id as user_message_id,
        m_user.content_blocks as user_content_blocks
    FROM messages m_assistant
    JOIN messages m_user ON m_assistant.reply_to = m_user.id
    WHERE m_assistant.role = 'assistant'
        AND m_assistant.status = 'done'
        AND m_user.status = 'done'
    ORDER BY m_assistant.created_at DESC
    LIMIT %s
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"查询失败: {e}", file=sys.stderr)
        return []


def analyze_content_blocks(content_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """分析 content_blocks 的结构"""
    if not content_blocks:
        return {
            "block_types": [],
            "has_text": False,
            "has_tool_use": False,
            "has_tool_result": False,
            "has_attachment": False,
            "tool_use_count": 0,
            "tool_names": [],
            "server_names": [],
        }

    block_types = []
    has_text = False
    has_tool_use = False
    has_tool_result = False
    has_attachment = False
    tool_use_count = 0
    tool_names = []
    server_names = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "unknown")
        block_types.append(block_type)

        if block_type == "text":
            has_text = True
        elif block_type == "tool_use":
            has_tool_use = True
            tool_use_count += 1
            # 提取工具信息
            tool_name = block.get("name", "")
            if tool_name:
                tool_names.append(tool_name)
            # 提取 server_name
            server_name = block.get("server_name", "")
            if server_name:
                server_names.append(server_name)
        elif block_type == "tool_result":
            has_tool_result = True
        elif block_type in ["image", "pdf", "markdown", "kb_context"]:
            has_attachment = True

    return {
        "block_types": block_types,
        "has_text": has_text,
        "has_tool_use": has_tool_use,
        "has_tool_result": has_tool_result,
        "has_attachment": has_attachment,
        "tool_use_count": tool_use_count,
        "tool_names": tool_names,
        "server_names": server_names,
    }


def classify_by_interaction_pattern(analysis: dict[str, Any]) -> str:
    """按交互模式分类"""
    has_text = analysis["has_text"]
    has_tool_use = analysis["has_tool_use"]
    has_tool_result = analysis["has_tool_result"]
    has_attachment = analysis["has_attachment"]
    tool_use_count = analysis["tool_use_count"]

    # 附件模式优先级最高
    if has_attachment:
        return "attachment"

    # 纯文本问答
    if has_text and not has_tool_use and not has_tool_result:
        return "simple_chat"

    # 工具调用模式
    if has_tool_use and has_tool_result:
        if tool_use_count == 1:
            return "single_tool"
        elif tool_use_count >= 2:
            return "multi_tool"

    # 其他情况（只有 tool_use 或只有 tool_result）
    if has_tool_use or has_tool_result:
        return "single_tool"

    return "unknown"


def classify_by_tool_type(analysis: dict[str, Any]) -> list[str]:
    """按工具类型分类"""
    tool_names = analysis["tool_names"]
    server_names = analysis["server_names"]

    if not tool_names:
        return []

    tool_types = []

    for tool_name in tool_names:
        tool_name_lower = tool_name.lower()

        # 根据工具名称分类
        if "tavily" in tool_name_lower or "search" in tool_name_lower:
            tool_types.append("tavily_search")
        elif "web" in tool_name_lower and ("extract" in tool_name_lower or "page" in tool_name_lower):
            tool_types.append("web_pages_extract")
        elif "shell" in tool_name_lower or "exec" in tool_name_lower or "command" in tool_name_lower:
            tool_types.append("shell")
        elif "file" in tool_name_lower:
            tool_types.append("file_operations")
        elif "weather" in tool_name_lower:
            tool_types.append("weather")
        elif "time" in tool_name_lower:
            tool_types.append("time")
        else:
            tool_types.append("other")

    # 如果有 server_name，可以更精确分类
    for server_name in server_names:
        if server_name and server_name not in ["tavily", "shell", "file", "weather", "time"]:
            if "other" not in tool_types:
                tool_types.append("mcp_server")

    return list(set(tool_types)) if tool_types else ["no_tool"]


def main():
    # 连接数据库
    conn = get_db_connection()

    # 获取问答对
    print("正在从数据库获取问答对...", file=sys.stderr)
    qa_pairs = fetch_qa_pairs_with_content_blocks(conn, limit=2000)
    print(f"获取到 {len(qa_pairs)} 条问答对", file=sys.stderr)

    if not qa_pairs:
        print("没有数据可分析", file=sys.stderr)
        conn.close()
        return

    # 分类统计
    interaction_patterns = Counter()
    tool_types = Counter()
    tool_usage = Counter()
    server_usage = Counter()

    # 详细分类结果
    classified_data = []

    for qa in qa_pairs:
        # 分析 assistant 的 content_blocks
        assistant_content_blocks = qa.get("content_blocks", [])
        analysis = analyze_content_blocks(assistant_content_blocks)

        # 分类
        interaction_pattern = classify_by_interaction_pattern(analysis)
        tool_types_list = classify_by_tool_type(analysis)

        # 更新统计
        interaction_patterns[interaction_pattern] += 1
        for tool_type in tool_types_list:
            tool_types[tool_type] += 1

        # 统计工具使用
        for tool_name in analysis["tool_names"]:
            tool_usage[tool_name] += 1
        for server_name in analysis["server_names"]:
            server_usage[server_name] += 1

        # 保存分类结果
        classified_qa = {
            "assistant_message_id": qa["assistant_message_id"],
            "user_message_id": qa["user_message_id"],
            "interaction_pattern": interaction_pattern,
            "tool_types": tool_types_list,
            "block_types": analysis["block_types"],
            "tool_use_count": analysis["tool_use_count"],
            "tool_names": analysis["tool_names"],
            "server_names": analysis["server_names"],
            "has_attachment": analysis["has_attachment"],
        }
        classified_data.append(classified_qa)

    # 输出统计结果
    print("\n" + "=" * 70)
    print("对话数据分类统计")
    print("=" * 70)

    print("\nA. 按交互模式分类:")
    print("-" * 40)
    for pattern, count in interaction_patterns.most_common():
        percentage = (count / len(qa_pairs)) * 100
        print(f"{pattern:<20} {count:>4} ({percentage:>5.1f}%)")

    print("\nB. 按工具类型分类:")
    print("-" * 40)
    for tool_type, count in tool_types.most_common():
        percentage = (count / len(qa_pairs)) * 100
        print(f"{tool_type:<20} {count:>4} ({percentage:>5.1f}%)")

    print("\nC. 工具使用频率 (Top 10):")
    print("-" * 40)
    for tool_name, count in tool_usage.most_common(10):
        print(f"{tool_name:<30} {count:>4}")

    print("\nD. MCP Server 使用频率:")
    print("-" * 40)
    for server_name, count in server_usage.most_common():
        print(f"{server_name:<30} {count:>4}")

    # 输出详细分类数据
    output_file = "scripts/classified_qa_data_detailed.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, ensure_ascii=False, indent=2)

    print(f"\n详细分类数据已保存到: {output_file}")

    conn.close()


if __name__ == "__main__":
    main()
