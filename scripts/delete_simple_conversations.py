#!/usr/bin/env python3
"""
删除简单对话的 conversation_id
包括删除相关的 messages 和 conversations 记录
"""

import json
import sys
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


def load_simple_conversation_ids():
    """从文件中加载简单对话的 conversation_id"""
    try:
        with open('scripts/simple_conversations.json', 'r') as f:
            data = json.load(f)
        # 去重
        unique_ids = list(set(data['conversation_ids']))
        return unique_ids
    except Exception as e:
        print(f"加载简单对话数据失败: {e}", file=sys.stderr)
        return []


def get_conversation_stats(conn, conversation_ids: list[str]):
    """获取要删除的对话的统计信息"""
    if not conversation_ids:
        return {}

    placeholders = ','.join(['%s'] * len(conversation_ids))

    query = f"""
    SELECT
        c.id,
        c.title,
        c.user_id,
        c.created_at,
        COUNT(m.id) as message_count
    FROM conversations c
    LEFT JOIN messages m ON c.id = m.conversation_id
    WHERE c.id IN ({placeholders})
    GROUP BY c.id, c.title, c.user_id, c.created_at
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, conversation_ids)
            rows = cur.fetchall()
            return {row['id']: row for row in rows}
    except Exception as e:
        print(f"获取对话统计失败: {e}", file=sys.stderr)
        return {}


def delete_conversations(conn, conversation_ids: list[str], dry_run: bool = True):
    """删除对话及其相关消息"""
    if not conversation_ids:
        print("没有要删除的对话", file=sys.stderr)
        return 0, 0

    placeholders = ','.join(['%s'] * len(conversation_ids))

    try:
        with conn.cursor() as cur:
            # 1. 统计要删除的消息数量
            cur.execute(f"""
                SELECT COUNT(*)
                FROM messages
                WHERE conversation_id IN ({placeholders})
            """, conversation_ids)
            message_count = cur.fetchone()[0]

            # 2. 统计要删除的对话数量
            cur.execute(f"""
                SELECT COUNT(*)
                FROM conversations
                WHERE id IN ({placeholders})
            """, conversation_ids)
            conversation_count = cur.fetchone()[0]

            print(f"\n{'[DRY RUN] ' if dry_run else ''}删除统计:", file=sys.stderr)
            print(f"  - 对话数量: {conversation_count}", file=sys.stderr)
            print(f"  - 消息数量: {message_count}", file=sys.stderr)

            if dry_run:
                print("\n[DRY RUN] 未执行实际删除操作", file=sys.stderr)
                return conversation_count, message_count

            # 3. 删除消息（由于外键约束，需要先删除消息）
            cur.execute(f"""
                DELETE FROM messages
                WHERE conversation_id IN ({placeholders})
            """, conversation_ids)
            deleted_messages = cur.rowcount

            # 4. 删除对话
            cur.execute(f"""
                DELETE FROM conversations
                WHERE id IN ({placeholders})
            """, conversation_ids)
            deleted_conversations = cur.rowcount

            # 5. 提交事务
            conn.commit()

            print(f"\n✅ 删除完成:", file=sys.stderr)
            print(f"  - 删除对话: {deleted_conversations} 个", file=sys.stderr)
            print(f"  - 删除消息: {deleted_messages} 条", file=sys.stderr)

            return deleted_conversations, deleted_messages

    except Exception as e:
        print(f"删除操作失败: {e}", file=sys.stderr)
        conn.rollback()
        return 0, 0


def main():
    # 加载简单对话 ID
    conversation_ids = load_simple_conversation_ids()

    if not conversation_ids:
        print("没有找到要删除的对话 ID", file=sys.stderr)
        sys.exit(1)

    print(f"找到 {len(conversation_ids)} 个简单对话要删除", file=sys.stderr)

    # 连接数据库
    conn = get_db_connection()

    # 获取对话统计信息
    stats = get_conversation_stats(conn, conversation_ids)

    if stats:
        print("\n要删除的对话详情:", file=sys.stderr)
        for i, (cid, info) in enumerate(stats.items(), 1):
            print(f"{i:2d}. {info['title'][:40]:<40} | 消息数: {info['message_count']} | ID: {cid}", file=sys.stderr)
            if i >= 10:
                print(f"    ... 还有 {len(stats) - 10} 个对话", file=sys.stderr)
                break

    # 先执行 dry run
    print("\n" + "="*60, file=sys.stderr)
    print("第一步: DRY RUN（预览删除操作）", file=sys.stderr)
    print("="*60, file=sys.stderr)

    conv_count, msg_count = delete_conversations(conn, conversation_ids, dry_run=True)

    # 询问用户确认
    print("\n" + "="*60, file=sys.stderr)
    print("第二步: 确认删除", file=sys.stderr)
    print("="*60, file=sys.stderr)

    # 输出 JSON 结果供程序使用
    result = {
        "conversation_ids": conversation_ids,
        "stats": {
            "conversations_to_delete": conv_count,
            "messages_to_delete": msg_count,
        },
        "details": {cid: {
            "title": info['title'],
            "message_count": info['message_count'],
            "user_id": info['user_id'],
            "created_at": info['created_at'].isoformat() if info['created_at'] else None,
        } for cid, info in stats.items()},
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
