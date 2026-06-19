#!/usr/bin/env python3
"""
执行删除 conversation_title 以 "dev-" 开头的对话
"""

import json
import sys

import psycopg2

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


def get_dev_conversation_ids(conn):
    """获取 title 以 dev- 开头的对话 ID"""
    query = """
    SELECT id
    FROM conversations
    WHERE title LIKE 'dev-%'
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows]
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

    # 获取 dev- 开头的对话 ID
    conversation_ids = get_dev_conversation_ids(conn)

    if not conversation_ids:
        print("没有找到 title 以 dev- 开头的对话", file=sys.stderr)
        conn.close()
        return

    print(f"准备删除 {len(conversation_ids)} 个 title 以 dev- 开头的对话", file=sys.stderr)

    # 执行删除
    deleted_conversations, deleted_messages = delete_conversations(conn, conversation_ids)

    if deleted_conversations > 0:
        print(f"\n✅ 删除成功!", file=sys.stderr)
        print(f"   - 删除对话: {deleted_conversations} 个", file=sys.stderr)
        print(f"   - 删除消息: {deleted_messages} 条", file=sys.stderr)

        # 输出 JSON 结果
        result = {
            "success": True,
            "deleted_conversations": deleted_conversations,
            "deleted_messages": deleted_messages,
            "conversation_ids": conversation_ids,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n❌ 删除失败", file=sys.stderr)
        result = {
            "success": False,
            "deleted_conversations": 0,
            "deleted_messages": 0,
            "conversation_ids": conversation_ids,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
