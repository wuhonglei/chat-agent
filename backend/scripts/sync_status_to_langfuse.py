#!/usr/bin/env python3
"""
将 production messages.status 同步到 Langfuse Score。

用法:
    export LANGFUSE_HOST="https://langfuse.wuhonglei.cn"
    export LANGFUSE_PUBLIC_KEY="pk-lf-xxx"
    export LANGFUSE_SECRET_KEY=***    export DB_HOST="134.175.182.235"
    export DB_USER="wuhonglei"
    export DB_PASSWORD=***    export DB_NAME="ai_assistant_db"

    python sync_status_to_langfuse.py              # 增量同步
    python sync_status_to_langfuse.py --dry-run     # 仅预览
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

# status -> score value 映射
STATUS_SCORE_MAP = {
    "done": 1.0,
    "stopped": 0.5,
    "failed": 0.0,
}


def make_trace_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:32]


def fetch_assistant_messages(conn: psycopg2.extensions.connection) -> list[Any]:
    query = """
        SELECT
            m.id AS message_id,
            m.conversation_id,
            m.status,
            m.created_at,
            m.updated_at,
            c.user_id
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.role = 'assistant'
          AND m.status IN ('done', 'stopped', 'failed')
        ORDER BY m.created_at DESC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cast(list[Any], cur.fetchall())


def create_langfuse_score(
    *,
    trace_id: str,
    name: str,
    value: float,
    comment: str = "",
) -> dict[str, Any]:
    url = f"{LANGFUSE_HOST}/api/public/scores"
    payload = {
        "traceId": trace_id,
        "name": name,
        "value": value,
        "source": "BACKEND",
        "comment": comment,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

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
    parser = argparse.ArgumentParser(description="Sync messages.status to Langfuse Score")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prod", action="store_true", help="连接生产数据库 (134.175.182.235)")
    args = parser.parse_args()

    global DB_HOST
    if args.prod:
        DB_HOST = "134.175.182.235"

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("ERROR: 请设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY")
        sys.exit(1)
    if not DB_PASSWORD:
        print("ERROR: 请设置 DB_PASSWORD")
        sys.exit(1)

    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )

    try:
        messages = fetch_assistant_messages(conn)
        print(f"Found {len(messages)} assistant messages (done/stopped/failed)")

        stats = {"done": 0, "stopped": 0, "failed": 0}
        success_count = 0
        error_count = 0

        for msg in messages:
            status = msg["status"]
            score_value = STATUS_SCORE_MAP.get(status)
            if score_value is None:
                continue

            trace_id = make_trace_id(msg["message_id"])
            stats[status] += 1

            if args.dry_run:
                print(f"  [DRY-RUN] trace={trace_id} status={status} value={score_value}")
                success_count += 1
                continue

            result = create_langfuse_score(
                trace_id=trace_id,
                name="message_status",
                value=score_value,
                comment=json.dumps({
                    "message_id": msg["message_id"],
                    "status": status,
                    "updated_at": str(msg["updated_at"]),
                }),
            )

            if "error" in result:
                print(f"  [ERROR] msg={msg['message_id'][:12]}... {result['error']}")
                error_count += 1
            else:
                success_count += 1

        print(f"\nStats: done={stats['done']}, stopped={stats['stopped']}, failed={stats['failed']}")
        print(f"Synced: {success_count}, Errors: {error_count}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
