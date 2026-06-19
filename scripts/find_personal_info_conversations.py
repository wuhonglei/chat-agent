#!/usr/bin/env python3
"""
查找与"你是谁"、"我是谁"、"我的个人信息、家庭信息"相关的对话
"""

import json
import re
import sys
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


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


def is_personal_info_question(text: str) -> bool:
    """判断是否为个人信息相关问题"""
    if not text:
        return False

    text = text.strip().lower()

    # 身份询问模式
    identity_patterns = [
        r"^(你是谁|你叫什么|who are you|what.*your name|你的名字|自我介绍|介绍一下你自己)",
        r"^(我是谁|我叫什么|who am i|what.*my name|我的名字)",
        r"(我的个人信息|我的家庭信息|我的隐私|我的资料)",
        r"(个人资料|家庭情况|家庭成员|家人)",
        r"(我是什么人|我的身份|我的角色)",
    ]

    for pattern in identity_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def find_personal_info_conversations(conn, limit: int = 5000):
    """查找个人信息相关的对话"""
    query = """
    SELECT
        c.id as conversation_id,
        c.title as conversation_title,
        m_user.id as user_message_id,
        m_user.content_blocks as user_content,
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
    # 连接数据库
    conn = get_db_connection()

    # 查找对话
    print("正在查找个人信息相关的对话...", file=sys.stderr)
    rows = find_personal_info_conversations(conn, limit=5000)
    print(f"检查了 {len(rows)} 条对话记录", file=sys.stderr)

    personal_info_conversations = []

    for row in rows:
        user_text = extract_text_from_content_blocks(row["user_content"])

        if is_personal_info_question(user_text):
            personal_info_conversations.append({
                "conversation_id": row["conversation_id"],
                "conversation_title": row["conversation_title"],
                "user_question": user_text,
                "user_created_at": row["user_created_at"].isoformat() if row["user_created_at"] else None,
            })

    print(f"找到 {len(personal_info_conversations)} 个个人信息相关的对话", file=sys.stderr)

    # 输出结果
    result = {
        "total_personal_info_conversations": len(personal_info_conversations),
        "conversation_ids": [c["conversation_id"] for c in personal_info_conversations],
        "details": personal_info_conversations,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
