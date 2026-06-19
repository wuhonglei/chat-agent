#!/usr/bin/env python3
"""scripts 目录共享的 Nacos YAML 配置加载工具。"""

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


def connect_database(
    config: dict[str, Any],
    *,
    exit_on_error: bool = True,
) -> Optional[psycopg2.extensions.connection]:
    """从配置获取 PostgreSQL 数据库连接"""
    db = config.get("database", {})

    if not db:
        print("❌ 配置中缺少 database 配置", file=sys.stderr)
        if exit_on_error:
            sys.exit(1)
        return None

    try:
        return psycopg2.connect(
            host=db.get("host"),
            port=db.get("port", 5432),
            user=db.get("username"),
            password=db.get("password"),
            dbname=db.get("db"),
        )
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}", file=sys.stderr)
        if exit_on_error:
            sys.exit(1)
        return None


def get_langfuse_credentials(config: dict[str, Any]) -> dict[str, str]:
    """从配置提取 Langfuse 连接凭证"""
    lf = config.get("langfuse", {})
    return {
        "host": lf.get("host", ""),
        "public_key": lf.get("public_key", ""),
        "secret_key": lf.get("secret_key", ""),
    }


def get_provider_credentials(config: dict[str, Any], provider: str) -> dict[str, str]:
    """从配置提取模型供应商 API 凭证"""
    provider_cfg = config.get("models", {}).get("providers", {}).get(provider, {})
    return {
        "api_key": provider_cfg.get("api_key", ""),
        "api_base": provider_cfg.get("base_url", ""),
    }


def get_frontend_chat_url(config: dict[str, Any]) -> str:
    """从 CORS 配置推断前端聊天页 URL"""
    origins = config.get("cors", {}).get("allow_origins", [])
    for origin in origins:
        if isinstance(origin, str) and origin.startswith("https://") and "localhost" not in origin:
            return f"{origin.rstrip('/')}/chat"
    return ""
