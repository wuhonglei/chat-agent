#!/usr/bin/env python3
"""
将 production messages.feedback 同步到 Langfuse Score。

用法:
    # 先设置环境变量（或直接修改下方配置）
    export LANGFUSE_HOST="https://langfuse.wuhonglei.cn"
    export LANGFUSE_PUBLIC_KEY="pk-lf-xxx"
    export LANGFUSE_SECRET_KEY="sk-lf-xxx"
    export DB_HOST="134.175.182.235"
    export DB_USER="wuhonglei"
    export DB_PASSWORD="xxx"
    export DB_NAME="ai_assistant_db"

    python sync_feedback_to_langfuse.py              # 增量同步（只同步未打分的）
    python sync_feedback_to_langfuse.py --full        # 全量同步
    python sync_feedback_to_langfuse.py --dry-run     # 仅预览，不实际写入
    python sync_feedback_to_langfuse.py --prod --dry-run  # 连 prod DB 预览
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.request
from typing import Any, cast

import psycopg2
import yaml
from psycopg2.extras import RealDictCursor

# ── 从 nacos 配置文件读取 ──────────────────────────────
NACOS_CONFIG_PATH = os.getenv(
    "NACOS_CONFIG",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "nacos-data",
        "config",
        "ai-chat-dev@@DEFAULT_GROUP@@",
    ),
)


def load_nacos_config() -> dict[str, Any]:
    """从 nacos yaml 配置文件加载 langfuse 和 database 配置。"""
    config_path = os.path.abspath(NACOS_CONFIG_PATH)
    if not os.path.exists(config_path):
        print(f"ERROR: nacos config not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return cast(dict[str, Any], cfg) if isinstance(cfg, dict) else {}


_cfg = load_nacos_config()
_lf = _cfg.get("langfuse", {})
_db = _cfg.get("database", {})

LANGFUSE_HOST = _lf.get("host", "")
LANGFUSE_PUBLIC_KEY = _lf.get("public_key", "")
LANGFUSE_SECRET_KEY = _lf.get("secret_key", "")

DB_HOST = _db.get("host", "")
DB_PORT = int(_db.get("port", 5432))
DB_USER = _db.get("username", "")
DB_PASSWORD = _db.get("password", "")
DB_NAME = _db.get("db", "")

# feedback.value 到 Langfuse score value 的映射
FEEDBACK_SCORE_MAP = {
    "like": 1.0,
    "dislike": 0.0,
    "default": None,  # 跳过未评分
}


def make_trace_id(seed: str) -> str:
    """与后端 new_trace_id(assistant_message_id) 保持一致。"""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:32]


def fetch_feedback_messages(conn: psycopg2.extensions.connection) -> list[Any]:
    """从 DB 读取所有有 feedback 的 assistant 消息。"""
    query = """
        SELECT
            m.id AS message_id,
            m.conversation_id,
            m.feedback,
            m.created_at,
            m.updated_at,
            m.status,
            c.user_id
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.role = 'assistant'
          AND m.feedback IS NOT NULL
          AND m.feedback->>'value' != 'default'
        ORDER BY m.created_at DESC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cast(list[Any], cur.fetchall())


def fetch_langfuse_trace_ids() -> set[str]:
    """从 Langfuse API 获取所有已存在的 trace ID。"""
    import base64

    url = f"{LANGFUSE_HOST}/api/public/traces?limit=50"
    req = urllib.request.Request(url)
    credentials = base64.b64encode(
        f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    req.add_header("Authorization", f"Basic {credentials}")

    trace_ids = set()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            for t in data.get("data", []):
                trace_ids.add(t["id"])
    except Exception as e:
        print(f"WARNING: Failed to fetch Langfuse traces: {e}")

    return trace_ids


def create_langfuse_score(
    *,
    trace_id: str,
    name: str,
    value: float,
    comment: str = "",
    source: str = "BACKEND",
) -> dict[str, Any]:
    """通过 Langfuse REST API 创建 score。"""
    url = f"{LANGFUSE_HOST}/api/public/scores"
    payload = {
        "traceId": trace_id,
        "name": name,
        "value": value,
        "source": source,
        "comment": comment,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    # Basic Auth: public_key:secret_key
    credentials = base64.b64encode(
        f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    req.add_header("Authorization", f"Basic {credentials}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode()))
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync messages.feedback to Langfuse Score")
    parser.add_argument("--full", action="store_true", help="全量同步（忽略增量检查）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际写入")
    parser.add_argument("--prod", action="store_true", help="连接生产数据库 (134.175.182.235)")
    args = parser.parse_args()

    global DB_HOST
    if args.prod:
        DB_HOST = "134.175.182.235"

    # 校验配置
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("ERROR: 请设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY 环境变量")
        sys.exit(1)
    if not DB_PASSWORD:
        print("ERROR: 请设置 DB_PASSWORD 环境变量")
        sys.exit(1)

    # 连接 DB
    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    try:
        messages = fetch_feedback_messages(conn)
        print(f"Found {len(messages)} messages with feedback (like/dislike)")

        if not messages:
            print("No feedback to sync.")
            return

        # 获取 Langfuse 中已存在的 trace ID
        existing_traces = fetch_langfuse_trace_ids()
        print(f"Langfuse has {len(existing_traces)} existing traces")

        success_count = 0
        skip_count = 0
        error_count = 0
        no_trace_count = 0

        for msg in messages:
            feedback = msg["feedback"]
            fb_value = feedback.get("value", "default")
            score_value = FEEDBACK_SCORE_MAP.get(fb_value)

            if score_value is None:
                skip_count += 1
                continue

            trace_id = make_trace_id(msg["message_id"])

            # 检查 trace 是否存在于 Langfuse
            if trace_id not in existing_traces:
                no_trace_count += 1
                if args.dry_run:
                    print(f"  [SKIP] trace={trace_id} not in Langfuse msg={msg['message_id'][:12]}...")
                continue

            updated_at = feedback.get("updated_at")

            comment = json.dumps(
                {
                    "message_id": msg["message_id"],
                    "conversation_id": msg["conversation_id"],
                    "feedback_updated_at": updated_at,
                    "status": msg["status"],
                },
                default=str,
            )

            if args.dry_run:
                print(
                    f"  [DRY-RUN] trace={trace_id} "
                    f"score=feedback value={score_value} "
                    f"msg={msg['message_id'][:12]}..."
                )
                success_count += 1
                continue

            result = create_langfuse_score(
                trace_id=trace_id,
                name="user_feedback",
                value=score_value,
                comment=comment,
            )

            if "error" in result:
                print(
                    f"  [ERROR] msg={msg['message_id'][:12]}... "
                    f"trace={trace_id} error={result['error']}"
                )
                error_count += 1
            else:
                print(
                    f"  [OK] trace={trace_id} "
                    f"score=feedback value={score_value} "
                    f"msg={msg['message_id'][:12]}..."
                )
                success_count += 1

        print(f"\nDone: {success_count} synced, {skip_count} skipped, {no_trace_count} no trace, {error_count} errors")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
