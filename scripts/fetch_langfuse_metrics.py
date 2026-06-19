#!/usr/bin/env python3
"""
从 Langfuse 获取 live 环境的 trace 数据
包含工具调用延迟、模型调用延迟等详细指标
"""

import base64
import json
import sys
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from nacos_config import get_langfuse_credentials, load_nacos_config


def _langfuse_headers(public_key: str, secret_key: str) -> dict[str, str]:
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }


def get_langfuse_traces(
    langfuse_config: dict[str, str],
    days: int = 7,
    limit: int = 1000,
) -> Optional[dict[str, Any]]:
    """从 Langfuse 获取 traces"""
    host = langfuse_config["host"]
    url = f"{host}/api/public/traces"

    headers = _langfuse_headers(
        langfuse_config["public_key"],
        langfuse_config["secret_key"],
    )

    params = {
        "limit": limit,
        "page": 1,
        "from_timestamp": (datetime.now() - timedelta(days=days)).isoformat(),
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取 Langfuse traces 失败: {e}", file=sys.stderr)
        return None


def get_trace_details(langfuse_config: dict[str, str], trace_id: str) -> Optional[dict[str, Any]]:
    """获取单个 trace 的详细信息"""
    url = f"{langfuse_config['host']}/api/public/traces/{trace_id}"

    headers = _langfuse_headers(
        langfuse_config["public_key"],
        langfuse_config["secret_key"],
    )

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取 trace {trace_id} 详情失败: {e}", file=sys.stderr)
        return None


def get_trace_observations(langfuse_config: dict[str, str], trace_id: str) -> Optional[dict[str, Any]]:
    """获取 trace 的 observations"""
    url = f"{langfuse_config['host']}/api/public/observations"

    headers = _langfuse_headers(
        langfuse_config["public_key"],
        langfuse_config["secret_key"],
    )

    params = {"traceId": trace_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取 trace {trace_id} observations 失败: {e}", file=sys.stderr)
        return None


def extract_metrics_from_trace(trace: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """从 trace 和 observations 中提取指标"""
    metrics: dict[str, Any] = {
        "trace_id": trace["id"],
        "name": trace.get("name", ""),
        "user_id": trace.get("userId", ""),
        "timestamp": trace.get("timestamp"),
        "latency_ms": trace.get("latency"),
        "model_calls": [],
        "tool_calls": [],
        "total_latency_ms": 0,
    }

    for obs in observations:
        obs_type = obs.get("type", "")
        latency_ms = obs.get("latency")

        if obs_type == "GENERATION":
            metrics["model_calls"].append({
                "id": obs["id"],
                "name": obs.get("name", ""),
                "latency_ms": latency_ms,
                "input": obs.get("input"),
                "output": obs.get("output"),
                "metadata": obs.get("metadata"),
            })

            # 检查是否是工具调用
            if "tool" in obs.get("name", "").lower() or "mcp" in obs.get("name", "").lower():
                metrics["tool_calls"].append({
                    "id": obs["id"],
                    "name": obs.get("name", ""),
                    "latency_ms": latency_ms,
                    "input": obs.get("input"),
                    "output": obs.get("output"),
                })

    # 计算总延迟
    if metrics["model_calls"]:
        total_latency = sum(call["latency_ms"] for call in metrics["model_calls"] if call["latency_ms"])
        metrics["total_latency_ms"] = total_latency

    return metrics


def main():
    config = load_nacos_config(prod=True)
    langfuse_config = get_langfuse_credentials(config)

    if not all(langfuse_config.values()):
        print("❌ 配置中缺少 langfuse 凭证", file=sys.stderr)
        sys.exit(1)

    print("正在从 Langfuse 获取 trace 数据...", file=sys.stderr)
    traces_data = get_langfuse_traces(langfuse_config, days=7, limit=100)

    if not traces_data:
        print("无法获取 Langfuse 数据", file=sys.stderr)
        sys.exit(1)

    traces = traces_data.get("data", [])
    print(f"获取到 {len(traces)} 个 traces", file=sys.stderr)

    all_metrics = []

    for i, trace in enumerate(traces[:10]):  # 先处理前10个作为示例
        print(f"处理 trace {i+1}/{min(len(traces), 10)}: {trace['id']}", file=sys.stderr)

        # 获取 observations
        observations_data = get_trace_observations(langfuse_config, trace["id"])
        observations = observations_data.get("data", []) if observations_data else []

        # 提取指标
        metrics = extract_metrics_from_trace(trace, observations)
        all_metrics.append(metrics)

    # 输出 JSON 格式
    print(json.dumps(all_metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
