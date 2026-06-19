#!/usr/bin/env python3
"""
生成完整的对话数据分类报告
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


def fetch_qa_pairs_with_details(conn, limit: int = 2000):
    """获取问答对及其详细信息"""
    query = """
    SELECT
        c.id as conversation_id,
        c.title as conversation_title,
        m_assistant.id as assistant_message_id,
        m_assistant.content_blocks,
        m_assistant.message_metadata,
        m_assistant.created_at as assistant_created_at,
        m_user.id as user_message_id,
        m_user.content_blocks as user_content_blocks,
        m_user.created_at as user_created_at
    FROM conversations c
    JOIN messages m_assistant ON c.id = m_assistant.conversation_id
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
            tool_name = block.get("name", "")
            if tool_name:
                tool_names.append(tool_name)
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

    if has_attachment:
        return "attachment"

    if has_text and not has_tool_use and not has_tool_result:
        return "simple_chat"

    if has_tool_use and has_tool_result:
        if tool_use_count == 1:
            return "single_tool"
        elif tool_use_count >= 2:
            return "multi_tool"

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

    for server_name in server_names:
        if server_name and server_name not in ["tavily", "shell", "file", "weather", "time"]:
            if "other" not in tool_types:
                tool_types.append("mcp_server")

    return list(set(tool_types)) if tool_types else ["no_tool"]


def extract_user_question(user_content_blocks: list[dict[str, Any]]) -> str:
    """从用户 content_blocks 中提取问题文本"""
    if not user_content_blocks:
        return ""

    text_parts = []
    for block in user_content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return " ".join(text_parts).strip()


def main():
    # 连接数据库
    conn = get_db_connection()

    # 获取问答对
    print("正在从数据库获取问答对...", file=sys.stderr)
    qa_pairs = fetch_qa_pairs_with_details(conn, limit=2000)
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

    # 按交互模式分组的数据
    grouped_data = defaultdict(list)

    # 详细分类结果
    classified_data = []

    for qa in qa_pairs:
        # 分析 assistant 的 content_blocks
        assistant_content_blocks = qa.get("content_blocks", [])
        analysis = analyze_content_blocks(assistant_content_blocks)

        # 提取用户问题
        user_question = extract_user_question(qa.get("user_content_blocks", []))

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
            "conversation_id": qa["conversation_id"],
            "conversation_title": qa["conversation_title"],
            "assistant_message_id": qa["assistant_message_id"],
            "user_message_id": qa["user_message_id"],
            "user_question": user_question[:100] + "..." if len(user_question) > 100 else user_question,
            "interaction_pattern": interaction_pattern,
            "tool_types": tool_types_list,
            "block_types": analysis["block_types"],
            "tool_use_count": analysis["tool_use_count"],
            "tool_names": analysis["tool_names"],
            "server_names": analysis["server_names"],
            "has_attachment": analysis["has_attachment"],
            "user_created_at": qa["user_created_at"].isoformat() if qa["user_created_at"] else None,
            "assistant_created_at": qa["assistant_created_at"].isoformat() if qa["assistant_created_at"] else None,
        }
        classified_data.append(classified_qa)
        grouped_data[interaction_pattern].append(classified_qa)

    # 输出统计结果
    print("\n" + "=" * 80)
    print("对话数据分类报告")
    print("=" * 80)

    print(f"\n总计: {len(qa_pairs)} 条问答对")

    print("\n" + "=" * 80)
    print("A. 按交互模式分类")
    print("=" * 80)
    print(f"{'模式':<20} {'数量':>6} {'占比':>8} {'说明'}")
    print("-" * 80)

    pattern_descriptions = {
        "simple_chat": "纯文本问答（无工具调用）",
        "single_tool": "单轮工具调用",
        "multi_tool": "多轮工具调用（Agent 循环）",
        "attachment": "含附件（image/pdf/markdown）",
        "unknown": "未知模式",
    }

    for pattern, count in interaction_patterns.most_common():
        percentage = (count / len(qa_pairs)) * 100
        desc = pattern_descriptions.get(pattern, "")
        print(f"{pattern:<20} {count:>4} ({percentage:>5.1f}%) {desc}")

    print("\n" + "=" * 80)
    print("B. 按工具类型分类")
    print("=" * 80)
    print(f"{'工具类型':<20} {'数量':>6} {'占比':>8} {'说明'}")
    print("-" * 80)

    tool_type_descriptions = {
        "tavily_search": "网页搜索",
        "web_pages_extract": "网页抓取",
        "shell": "Shell 执行",
        "file_operations": "文件操作",
        "weather": "天气查询",
        "time": "时间查询",
        "mcp_server": "其他 MCP Server",
        "other": "其他工具",
        "no_tool": "无工具调用",
    }

    for tool_type, count in tool_types.most_common():
        percentage = (count / len(qa_pairs)) * 100
        desc = tool_type_descriptions.get(tool_type, "")
        print(f"{tool_type:<20} {count:>4} ({percentage:>5.1f}%) {desc}")

    print("\n" + "=" * 80)
    print("C. MCP Server 使用频率")
    print("=" * 80)
    print(f"{'Server 名称':<20} {'调用次数':>8} {'说明'}")
    print("-" * 80)

    server_descriptions = {
        "tavily": "网页搜索和抓取",
        "context7": "文档查询",
        "zread": "代码仓库读取",
        "file": "文件操作",
        "code": "代码执行",
        "shell": "Shell 命令执行",
        "skill_manager": "技能管理",
        "weather": "天气查询",
        "time": "时间查询",
    }

    for server_name, count in server_usage.most_common():
        desc = server_descriptions.get(server_name, "其他功能")
        print(f"{server_name:<20} {count:>4} {desc}")

    print("\n" + "=" * 80)
    print("D. 工具使用频率 (Top 15)")
    print("=" * 80)
    print(f"{'工具名称':<35} {'调用次数':>8}")
    print("-" * 80)

    for tool_name, count in tool_usage.most_common(15):
        print(f"{tool_name:<35} {count:>4}")

    # 输出详细分类数据
    output_file = "scripts/classified_qa_data_final.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, ensure_ascii=False, indent=2)

    print(f"\n详细分类数据已保存到: {output_file}")

    # 输出按交互模式分组的示例
    print("\n" + "=" * 80)
    print("E. 各类示例（每类前3个）")
    print("=" * 80)

    for pattern in ["simple_chat", "single_tool", "multi_tool"]:
        examples = grouped_data.get(pattern, [])[:3]
        if examples:
            print(f"\n{pattern} 示例:")
            for i, ex in enumerate(examples, 1):
                print(f"  {i}. {ex['conversation_title'][:40]}")
                print(f"     工具: {', '.join(ex['tool_names']) if ex['tool_names'] else '无'}")

    conn.close()


if __name__ == "__main__":
    main()
