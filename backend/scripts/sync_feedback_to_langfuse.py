#!/usr/bin/env python3
"""
将 messages.feedback 同步到 Langfuse Score。

用法:
    python sync_feedback_to_langfuse.py              # 使用 dev nacos 配置，增量同步
    python sync_feedback_to_langfuse.py --prod       # 使用 prod nacos 配置
    python sync_feedback_to_langfuse.py --full        # 全量同步
    python sync_feedback_to_langfuse.py --dry-run     # 仅预览，不实际写入
    python sync_feedback_to_langfuse.py --prod --dry-run  # 使用 prod nacos 配置预览

    # 也可通过环境变量指定配置文件
    export NACOS_CONFIG=/path/to/ai-chat-prod@@DEFAULT_GROUP@@
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
def _default_nacos_config_path(*, prod: bool) -> str:
    filename = "ai-chat-prod@@DEFAULT_GROUP@@" if prod else "ai-chat-dev@@DEFAULT_GROUP@@"
    return os.path.join(
        os.path.dirname(__file__),
        "..",
        "nacos-data",
        "config",
        filename,
    )


def resolve_nacos_config_path(*, prod: bool) -> str:
    env_path = os.getenv("NACOS_CONFIG")
    if env_path:
        return os.path.abspath(env_path)
    return os.path.abspath(_default_nacos_config_path(prod=prod))


def load_nacos_config(*, prod: bool) -> dict[str, Any]:
    """从 nacos yaml 配置文件加载 langfuse 和 database 配置。"""
    config_path = resolve_nacos_config_path(prod=prod)
    if not os.path.exists(config_path):
        print(f"ERROR: nacos config not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return cast(dict[str, Any], cfg) if isinstance(cfg, dict) else {}

# feedback.value 到 Langfuse score value 的映射
FEEDBACK_SCORE_MAP = {
    "like": 1.0,
    "dislike": 0.0,
    "default": None,  # 跳过未评分
}


def make_trace_id(seed: str) -> str:
    """与后端 new_trace_id(assistant_message_id) 保持一致。"""
    try:
        from langfuse import Langfuse
        return Langfuse.create_trace_id(seed=seed)
    except Exception:
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


def fetch_langfuse_trace_ids(
    *,
    langfuse_host: str,
    public_key: str,
    secret_key: str,
) -> set[str]:
    """从 Langfuse API 获取所有已存在的 trace ID。"""
    url = f"{langfuse_host}/api/public/traces?limit=50"
    req = urllib.request.Request(url)
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
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
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    trace_id: str,
    name: str,
    value: float,
    comment: str = "",
) -> dict[str, Any]:
    """通过 Langfuse REST API 创建 score。"""
    url = f"{langfuse_host}/api/public/scores"
    payload = {
        "traceId": trace_id,
        "name": name,
        "value": value,
        "source": "API",
        "comment": comment,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    # Basic Auth: public_key:secret_key
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
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
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用 ai-chat-prod nacos 配置（默认 ai-chat-dev）",
    )
    args = parser.parse_args()

    cfg = load_nacos_config(prod=args.prod)
    lf = cfg.get("langfuse", {})
    db = cfg.get("database", {})

    langfuse_host = lf.get("host", "")
    public_key = lf.get("public_key", "")
    secret_key = lf.get("secret_key", "")

    db_host = db.get("host", "")
    db_port = int(db.get("port", 5432))
    db_user = db.get("username", "")
    db_password = db.get("password", "")
    db_name = db.get("db", "")

    config_path = resolve_nacos_config_path(prod=args.prod)
    print(f"Using nacos config: {config_path}")

    # 校验配置
    if not public_key or not secret_key:
        print("ERROR: nacos 配置中缺少 langfuse.public_key / langfuse.secret_key")
        sys.exit(1)
    if not db_password:
        print("ERROR: nacos 配置中缺少 database.password")
        sys.exit(1)

    # 连接 DB
    print(f"Connecting to {db_host}:{db_port}/{db_name}...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
    )

    try:
        messages = fetch_feedback_messages(conn)
        print(f"Found {len(messages)} messages with feedback (like/dislike)")

        if not messages:
            print("No feedback to sync.")
            return

        # 获取 Langfuse 中已存在的 trace ID
        existing_traces = fetch_langfuse_trace_ids(
            langfuse_host=langfuse_host,
            public_key=public_key,
            secret_key=secret_key,
        )
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
                    "reasons": feedback.get("reasons") or [],
                    "comment": feedback.get("comment"),
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
                langfuse_host=langfuse_host,
                public_key=public_key,
                secret_key=secret_key,
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
