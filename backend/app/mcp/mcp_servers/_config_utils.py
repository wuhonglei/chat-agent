"""MCP Server 配置解包工具（无全局 settings 依赖）。"""

from __future__ import annotations


def require_env(env: dict[str, str], key: str) -> str:
    try:
        return env[key]
    except KeyError as exc:
        raise KeyError(f"Missing MCP server env key: {key!r}") from exc


def env_int(env: dict[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    return int(raw)
