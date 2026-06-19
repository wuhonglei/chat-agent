#!/usr/bin/env python3
"""
删除 conversation_title 以 "dev-" 开头的对话
"""

import json
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


def get_dev_conversations(conn):
    """获取 title 以 dev- 开头的对话"""
    query = """
    SELECT
        c.id,
        c.title,
        c.user_id,
        c.created_at,
        COUNT(m.id) as message_count
    FROM conversations c
    LEFT JOIN messages m ON c.id = m.conversation_id
    WHERE c.title LIKE 'dev-%'
    GROUP BY c.id, c.title, c.user_id, c.created_at
    ORDER BY c.created_at DESC
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return rows
    except Exception as e:
        print(f"查询失败: {e}", file=sys.stderr)
        return []


def delete_conversations(conn, conversation_ids: list[str]):
    """删除对话及其相关消息"""
    if not conversation_ids:
        print("没有要删除的对话", file=sys.stderr)
        return 0, 0

    placeholders = ','.join(['%s'] * len(conversation_ids))

    try:
        with conn.cursor() as cur:
            # 1. 删除消息
            cur.execute(f"""
                DELETE FROM messages
                WHERE conversation_id IN ({placeholders})
            """, conversation_ids)
            deleted_messages = cur.rowcount

            # 2. 删除对话
            cur.execute(f"""
                DELETE FROM conversations
                WHERE id IN ({placeholders})
            """, conversation_ids)
            deleted_conversations = cur.rowcount

            # 3. 提交事务
            conn.commit()

            return deleted_conversations, deleted_messages

    except Exception as e:
        print(f"删除操作失败: {e}", file=sys.stderr)
        conn.rollback()
        return 0, 0


def main():
    # 连接数据库
    conn = get_db_connection()

    # 获取 dev- 开头的对话
    dev_conversations = get_dev_conversations(conn)

    if not dev_conversations:
        print("没有找到 title 以 dev- 开头的对话", file=sys.stderr)
        conn.close()
        return

    print(f"找到 {len(dev_conversations)} 个 title 以 dev- 开头的对话", file=sys.stderr)

    # 统计消息总数
    total_messages = sum(conv['message_count'] for conv in dev_conversations)

    # 显示对话详情
    print("\n对话详情:", file=sys.stderr)
    for i, conv in enumerate(dev_conversations[:15], 1):
        print(f"{i:2d}. {conv['title'][:50]:<50} | 消息数: {conv['message_count']} | ID: {conv['id']}", file=sys.stderr)
        if i >= 15:
            print(f"    ... 还有 {len(dev_conversations) - 15} 个对话", file=sys.stderr)
            break

    # 准备删除的 ID 列表
    conversation_ids = [conv['id'] for conv in dev_conversations]

    # 输出统计信息
    result = {
        "conversation_ids": conversation_ids,
        "stats": {
            "conversations_to_delete": len(dev_conversations),
            "messages_to_delete": total_messages,
        },
        "details": {conv['id']: {
            "title": conv['title'],
            "message_count": conv['message_count'],
            "user_id": conv['user_id'],
            "created_at": conv['created_at'].isoformat() if conv['created_at'] else None,
        } for conv in dev_conversations},
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
