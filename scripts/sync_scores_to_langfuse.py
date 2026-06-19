#!/usr/bin/env python3
"""
Langfuse 评分同步脚本
将消息状态同步到 Langfuse Score
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Optional, Sequence

import psycopg2
import yaml
from psycopg2.extras import RealDictCursor


def load_nacos_config(prod: bool = True) -> dict[str, Any]:
    """从 nacos 配置文件加载配置"""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "backend",
        "nacos-data",
        "config",
        "ai-chat-prod@@DEFAULT_GROUP@@" if prod else "ai-chat-dev@@DEFAULT_GROUP@@",
    )

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}", file=sys.stderr)
        return {}

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}", file=sys.stderr)
        return {}


def get_db_connection(config: dict[str, Any]) -> Optional[psycopg2.extensions.connection]:
    """获取数据库连接"""
    db = config.get("database", {})

    if not db:
        print("❌ 配置中缺少 database 配置", file=sys.stderr)
        return None

    try:
        conn = psycopg2.connect(
            host=db.get("host"),
            port=db.get("port", 5432),
            user=db.get("username"),
            password=db.get("password"),
            dbname=db.get("db"),
        )
        return conn
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}", file=sys.stderr)
        return None


def fetch_messages_for_scoring(
    conn: psycopg2.extensions.connection,
    limit: int = 1000,
    offset: int = 0
) -> Sequence[dict[str, Any]]:
    """获取需要评分的消息"""
    query = """
    SELECT
        m.id as message_id,
        m.conversation_id,
        m.status,
        m.created_at,
        m.updated_at,
        c.user_id,
        c.title as conversation_title
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE m.role = 'assistant'
      AND m.status IN ('done', 'stopped', 'failed')
    ORDER BY m.created_at DESC
    LIMIT %s OFFSET %s
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (limit, offset))
            return cur.fetchall()
    except Exception as e:
        print(f"❌ 查询消息失败: {e}", file=sys.stderr)
        return []


def calculate_score_value(status: str) -> Optional[float]:
    """根据状态计算评分值"""
    score_map = {
        "done": 1.0,
        "stopped": 0.5,
        "failed": 0.0,
    }
    return score_map.get(status)


def create_trace_id(message_id: str) -> str:
    """生成确定性 trace_id"""
    import hashlib
    digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()
    return f"trace_{digest[:32]}"


def sync_score_to_langfuse(
    langfuse_client: Any,
    trace_id: str,
    message_data: dict[str, Any]
) -> bool:
    """同步评分到 Langfuse"""
    try:
        status = message_data["status"]
        score_value = calculate_score_value(status)

        if score_value is None:
            return True

        # 准备注释
        comment = json.dumps({
            "message_id": message_data["message_id"],
            "status": status,
            "conversation_id": message_data["conversation_id"],
            "updated_at": str(message_data["updated_at"]),
        }, ensure_ascii=False)

        # 创建 Score
        score = langfuse_client.score(
            trace_id=trace_id,
            name="message_status",
            value=score_value,
            comment=comment,
        )

        return True
    except Exception as e:
        print(f"❌ 同步评分失败: {e}", file=sys.stderr)
        return False


def sync_batch_scores(
    langfuse_client: Any,
    messages: Sequence[dict[str, Any]],
    batch_size: int = 50
) -> dict[str, Any]:
    """批量同步评分"""
    stats: dict[str, Any] = {
        "total": len(messages),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "elapsed_time": 0.0,
        "records_per_second": 0.0,
    }

    total_batches = (len(messages) + batch_size - 1) // batch_size

    print(f"\n开始同步 {stats['total']} 条评分...")
    print(f"批次大小: {batch_size}, 总批次数: {total_batches}")
    print("=" * 60)

    start_time = time.time()

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(messages))
        batch = messages[batch_start:batch_end]

        print(f"\n批次 {batch_idx + 1}/{total_batches} ({len(batch)} 条)")

        batch_success = 0
        batch_failed = 0
        batch_skipped = 0

        for message_data in batch:
            # 生成 trace_id
            trace_id = create_trace_id(message_data["message_id"])

            # 检查 trace 是否存在（简化处理，实际应查询 Langfuse）
            # 这里假设 trace 已存在，直接同步评分

            # 同步评分
            if sync_score_to_langfuse(langfuse_client, trace_id, message_data):
                batch_success += 1
            else:
                batch_failed += 1

        stats["success"] = stats["success"] + batch_success
        stats["failed"] = stats["failed"] + batch_failed
        stats["skipped"] = stats["skipped"] + batch_skipped

        print(f"  ✅ 成功: {batch_success}, ❌ 失败: {batch_failed}, ⏭️  跳过: {batch_skipped}")

        # 批次间延迟
        if batch_idx < total_batches - 1:
            time.sleep(1)

    elapsed_time = time.time() - start_time
    stats["elapsed_time"] = elapsed_time
    stats["records_per_second"] = stats["total"] / elapsed_time if elapsed_time > 0 else 0.0

    return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Langfuse 评分同步工具")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="批次大小 (默认: 50)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="最多同步 N 条消息 (默认: 1000)"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="跳过前 N 条消息 (默认: 0)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行，不实际同步"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Langfuse 评分同步工具")
    print("=" * 60)
    print(f"批次大小: {args.batch_size}")
    print(f"限制: {args.limit}")
    print(f"偏移量: {args.offset}")
    print(f"环境: {'生产' if args.prod else '开发'}")
    print(f"试运行: {'是' if args.dry_run else '否'}")

    # 加载配置
    config = load_nacos_config(prod=args.prod)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    lf_config = config.get("langfuse", {})

    if not lf_config.get("enabled"):
        print("❌ Langfuse 未启用", file=sys.stderr)
        sys.exit(1)

    # 初始化 Langfuse 客户端
    if not args.dry_run:
        try:
            from langfuse import Langfuse

            langfuse_client = Langfuse(
                public_key=lf_config.get("public_key"),
                secret_key=lf_config.get("secret_key"),
                host=lf_config.get("host"),
            )

            print(f"\n✅ Langfuse 客户端初始化成功")
            print(f"   Host: {lf_config.get('host')}")
        except Exception as e:
            print(f"❌ Langfuse 客户端初始化失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        langfuse_client = None
        print(f"\n⚠️  试运行模式，不实际同步")

    # 获取数据库连接
    conn = get_db_connection(config)

    if not conn:
        print("❌ 数据库连接失败", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅ 数据库连接成功")

    # 获取消息
    print(f"\n获取消息...")
    messages = fetch_messages_for_scoring(conn, limit=args.limit, offset=args.offset)

    if not messages:
        print("❌ 没有消息可同步", file=sys.stderr)
        conn.close()
        sys.exit(1)

    print(f"  - 获取到 {len(messages)} 条消息")

    # 试运行模式
    if args.dry_run:
        print(f"\n试运行模式，将同步 {len(messages)} 条评分")

        # 统计状态分布
        status_counts: dict[str, int] = {}
        for msg in messages:
            status = msg["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"\n状态分布:")
        for status, count in status_counts.items():
            print(f"  - {status}: {count} 条 ({count/len(messages)*100:.1f}%)")

        print("✅ 试运行完成")
        conn.close()
        return

    # 执行同步
    stats = sync_batch_scores(
        langfuse_client=langfuse_client,
        messages=messages,
        batch_size=args.batch_size,
    )

    # 刷新 Langfuse 缓冲区
    print("\n刷新 Langfuse 缓冲区...")
    try:
        if langfuse_client:
            langfuse_client.flush()
            print("✅ 缓冲区刷新成功")
    except Exception as e:
        print(f"⚠️  缓冲区刷新失败: {e}")

    # 关闭数据库连接
    conn.close()

    # 输出统计
    print("\n" + "=" * 60)
    print("同步完成统计")
    print("=" * 60)
    print(f"总消息数: {stats['total']}")
    print(f"成功同步: {stats['success']}")
    print(f"同步失败: {stats['failed']}")
    print(f"跳过: {stats['skipped']}")
    print(f"成功率: {stats['success']/stats['total']*100:.1f}%")
    print(f"总耗时: {stats['elapsed_time']:.1f} 秒")
    print(f"平均速度: {stats['records_per_second']:.1f} 条/秒")

    if stats['failed'] > 0:
        print(f"\n⚠️  有 {stats['failed']} 条评分同步失败，请检查日志")
    else:
        print(f"\n✅ 全部评分同步成功")


if __name__ == "__main__":
    main()
