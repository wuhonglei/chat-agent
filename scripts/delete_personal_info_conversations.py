#!/usr/bin/env python3
"""
删除个人信息相关的对话
"""

import json
import sys

import psycopg2

from nacos_config import connect_database, load_nacos_config


def get_db_connection():
    """创建数据库连接"""
    config = load_nacos_config(prod=True)
    return connect_database(config)


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
    # 从文件加载要删除的 conversation_id
    try:
        with open('scripts/personal_info_conversations.json', 'r') as f:
            data = json.load(f)
        conversation_ids = data['conversation_ids']
    except Exception as e:
        print(f"加载数据失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not conversation_ids:
        print("没有找到要删除的对话 ID", file=sys.stderr)
        return

    print(f"准备删除 {len(conversation_ids)} 个个人信息相关的对话", file=sys.stderr)

    # 连接数据库
    conn = get_db_connection()

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
