#!/usr/bin/env python3
"""
筛选出简单对话的 conversation_id
用于标识需要过滤的简单问答对话
"""

import json
import re
import sys
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from nacos_config import connect_database, load_nacos_config

# 简单问题过滤模式
SIMPLE_PATTERNS = [
    # 问候语
    r"^(你好|hello|hi|hey|嗨|哈喽|您好|早上好|下午好|晚上好)[\s!！。.？?]*$",
    # 身份询问
    r"^(你是谁|你叫什么|who are you|what.*your name|你的名字|自我介绍|介绍一下你自己)[\s!！。.？?]*$",
    # 天气相关
    r"(天气|气温|下雨|下雪|晴天|阴天|weather|temperature|forecast|今天.*天气|明天.*天气|.*的天气)",
    # 简单测试
    r"^(test|测试|ping|hello world|1\+1|1\+1等于几)[\s!！。.？?]*$",
    # 过短的问题（少于3个字符）
    r"^.{0,2}$",
]

# 编译正则模式
SIMPLE_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in SIMPLE_PATTERNS]


def is_simple_question(text: str) -> bool:
    """判断是否为简单问题"""
    if not text:
        return True
    text = text.strip()
    for pattern in SIMPLE_PATTERNS_COMPILED:
        if pattern.search(text):
            return True
    return False


def extract_text_from_content_blocks(content_blocks: list[dict[str, Any]]) -> str:
    """从 content_blocks 中提取文本内容"""
    if not content_blocks:
        return ""

    text_parts = []
    for block in content_blocks:
        if isinstance(block, dict):
            if "text" in block:
                text_parts.append(block["text"])
            elif "content" in block:
                text_parts.append(block["content"])
            elif "type" in block and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
    return " ".join(text_parts).strip()


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


def fetch_simple_conversations(conn, limit: int = 5000):
    """获取简单对话的 conversation_id"""
    query = """
    SELECT
        c.id as conversation_id,
        c.title as conversation_title,
        m_user.content_blocks,
        m_user.created_at as user_created_at
    FROM conversations c
    JOIN messages m_user ON c.id = m_user.conversation_id
        AND m_user.role = 'user'
    WHERE m_user.status = 'done'
    ORDER BY m_user.created_at DESC
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


def main():
    print("正在连接数据库...", file=sys.stderr)
    conn = get_db_connection()

    print("正在获取对话数据...", file=sys.stderr)
    rows = fetch_simple_conversations(conn, limit=5000)
    print(f"获取到 {len(rows)} 条对话记录", file=sys.stderr)

    simple_conversations = []

    for row in rows:
        user_text = extract_text_from_content_blocks(row["content_blocks"])

        if is_simple_question(user_text):
            simple_conversations.append({
                "conversation_id": row["conversation_id"],
                "conversation_title": row["conversation_title"],
                "user_question": user_text,
                "user_created_at": row["user_created_at"].isoformat() if row["user_created_at"] else None,
            })

    print(f"筛选出 {len(simple_conversations)} 个简单对话", file=sys.stderr)

    # 输出 JSON 格式
    result = {
        "total_simple_conversations": len(simple_conversations),
        "conversation_ids": [c["conversation_id"] for c in simple_conversations],
        "details": simple_conversations,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
