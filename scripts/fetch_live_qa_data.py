#!/usr/bin/env python3
"""
获取 live 环境问答数据用于 Langfuse 指标收集
过滤掉简单问题（你好、你是谁、天气相关等）
"""

import json
import re
import sys
from datetime import datetime
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
            # 尝试多种常见的内容字段
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


def fetch_qa_pairs(conn, limit: int = 1000):
    """获取问答对"""
    query = """
    WITH paired_messages AS (
        SELECT
            c.id as conversation_id,
            c.title as conversation_title,
            c.user_id,
            m_user.id as user_message_id,
            m_user.content_blocks as user_content,
            m_user.created_at as user_created_at,
            m_assistant.id as assistant_message_id,
            m_assistant.content_blocks as assistant_content,
            m_assistant.created_at as assistant_created_at,
            m_assistant.message_metadata as assistant_metadata
        FROM conversations c
        JOIN messages m_user ON c.id = m_user.conversation_id
            AND m_user.role = 'user'
        JOIN messages m_assistant ON c.id = m_assistant.conversation_id
            AND m_assistant.role = 'assistant'
            AND m_assistant.reply_to = m_user.id
        WHERE m_user.status = 'done'
            AND m_assistant.status = 'done'
        ORDER BY m_user.created_at DESC
        LIMIT %s
    )
    SELECT * FROM paired_messages
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"查询失败: {e}", file=sys.stderr)
        return []


def extract_tool_calls(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """从 message_metadata 中提取工具调用信息"""
    tool_calls = []
    if not metadata:
        return tool_calls

    # 检查常见的工具调用字段
    if "tool_calls" in metadata:
        for call in metadata["tool_calls"]:
            tool_calls.append({
                "name": call.get("name", "unknown"),
                "arguments": call.get("arguments", {}),
                "duration_ms": call.get("duration_ms"),
                "status": call.get("status", "unknown"),
            })

    return tool_calls


def process_qa_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """处理问答对，过滤简单问题，提取关键信息"""
    processed = []

    for row in rows:
        # 提取用户问题文本
        user_text = extract_text_from_content_blocks(row["user_content"])

        # 过滤简单问题
        if is_simple_question(user_text):
            continue

        # 提取助手回答文本
        assistant_text = extract_text_from_content_blocks(row["assistant_content"])

        # 提取工具调用信息
        tool_calls = extract_tool_calls(row["assistant_metadata"] or {})

        # 计算响应时间（如果有）
        user_time = row["user_created_at"]
        assistant_time = row["assistant_created_at"]
        response_time_ms = None
        if user_time and assistant_time:
            response_time_ms = int((assistant_time - user_time).total_seconds() * 1000)

        qa_pair = {
            "conversation_id": row["conversation_id"],
            "conversation_title": row["conversation_title"],
            "user_id": row["user_id"],
            "user_message_id": row["user_message_id"],
            "user_question": user_text,
            "user_question_length": len(user_text),
            "assistant_message_id": row["assistant_message_id"],
            "assistant_answer": assistant_text[:500] + "..." if len(assistant_text) > 500 else assistant_text,
            "assistant_answer_length": len(assistant_text),
            "response_time_ms": response_time_ms,
            "tool_calls_count": len(tool_calls),
            "tool_calls": tool_calls,
            "user_created_at": user_time.isoformat() if user_time else None,
            "assistant_created_at": assistant_time.isoformat() if assistant_time else None,
        }
        processed.append(qa_pair)

    return processed


def main():
    print("正在连接数据库...", file=sys.stderr)
    conn = get_db_connection()

    print("正在获取问答数据...", file=sys.stderr)
    rows = fetch_qa_pairs(conn, limit=2000)
    print(f"获取到 {len(rows)} 条原始问答对", file=sys.stderr)

    print("正在处理和过滤数据...", file=sys.stderr)
    processed = process_qa_pairs(rows)
    print(f"过滤后剩余 {len(processed)} 条问答对", file=sys.stderr)

    # 输出 JSON 格式
    print(json.dumps(processed, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
