#!/usr/bin/env python3
"""
验证 Langfuse 连接配置和环境
"""

import json
import os
import sys
from typing import Any, Optional

import psycopg2
import yaml


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


def test_langfuse_connection(config: dict[str, Any]) -> bool:
    """测试 Langfuse 连接"""
    lf = config.get("langfuse", {})

    if not lf:
        print("❌ 配置中缺少 langfuse 配置", file=sys.stderr)
        return False

    host = lf.get("host", "")
    public_key = lf.get("public_key", "")
    secret_key = lf.get("secret_key", "")
    enabled = lf.get("enabled", False)

    print("\n" + "=" * 60)
    print("Langfuse 配置检查")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Public Key: {public_key[:20]}..." if public_key else "Public Key: ❌ 缺失")
    print("Secret Key: ✅ 已配置" if secret_key else "Secret Key: ❌ 缺失")
    print(f"Enabled: {enabled}")

    if not host or not public_key or not secret_key:
        print("❌ Langfuse 配置不完整", file=sys.stderr)
        return False

    # 测试 API 连通性
    print("\n测试 Langfuse API 连通性...")
    try:
        import urllib.request
        import base64

        url = f"{host}/api/public/health"
        req = urllib.request.Request(url)
        credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        req.add_header("Authorization", f"Basic {credentials}")

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("✅ Langfuse API 连接成功")
                return True
            else:
                print(f"❌ Langfuse API 返回状态码: {resp.status}")
                return False
    except Exception as e:
        print(f"❌ Langfuse API 连接失败: {e}")
        return False


def test_database_connection(config: dict[str, Any]) -> bool:
    """测试数据库连接"""
    db = config.get("database", {})

    if not db:
        print("❌ 配置中缺少 database 配置", file=sys.stderr)
        return False

    host = db.get("host", "")
    port = db.get("port", 5432)
    username = db.get("username", "")
    password = db.get("password", "")
    database = db.get("db", "")

    print("\n" + "=" * 60)
    print("数据库配置检查")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Username: {username}")
    print(f"Database: {database}")
    print(f"Password: {'*' * len(password) if password else '❌ 缺失'}")

    if not host or not username or not password or not database:
        print("❌ 数据库配置不完整", file=sys.stderr)
        return False

    # 测试数据库连接
    print("\n测试数据库连接...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            dbname=database,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conversations")
            conv_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM messages")
            msg_count = cur.fetchone()[0]

            print(f"✅ 数据库连接成功")
            print(f"   - 对话数量: {conv_count}")
            print(f"   - 消息数量: {msg_count}")

        conn.close()
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def main():
    print("=" * 60)
    print("Langfuse 环境配置验证")
    print("=" * 60)

    # 加载配置
    config = load_nacos_config(prod=True)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    # 测试 Langfuse 连接
    langfuse_ok = test_langfuse_connection(config)

    # 测试数据库连接
    db_ok = test_database_connection(config)

    # 总结
    print("\n" + "=" * 60)
    print("环境配置验证结果")
    print("=" * 60)
    print(f"Langfuse 连接: {'✅ 成功' if langfuse_ok else '❌ 失败'}")
    print(f"数据库连接: {'✅ 成功' if db_ok else '❌ 失败'}")

    if langfuse_ok and db_ok:
        print("\n✅ 环境配置验证通过，可以开始数据导入")
        return True
    else:
        print("\n❌ 环境配置验证失败，请检查配置")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
