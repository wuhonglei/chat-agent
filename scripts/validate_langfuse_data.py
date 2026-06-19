#!/usr/bin/env python3
"""
验证 Langfuse 中导入的数据
"""

import json
import os
import sys
from typing import Any, Optional

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


def fetch_langfuse_traces(
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    limit: int = 100,
    page: int = 1
) -> dict[str, Any]:
    """从 Langfuse 获取 traces"""
    import urllib.request
    import base64

    url = f"{langfuse_host}/api/public/traces?limit={limit}&page={page}"
    req = urllib.request.Request(url)
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"❌ 获取 traces 失败: {e}", file=sys.stderr)
        return {}


def fetch_langfuse_observations(
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    trace_id: str
) -> dict[str, Any]:
    """从 Langfuse 获取 trace 的 observations"""
    import urllib.request
    import base64

    url = f"{langfuse_host}/api/public/observations?traceId={trace_id}"
    req = urllib.request.Request(url)
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"❌ 获取 observations 失败: {e}", file=sys.stderr)
        return {}


def validate_langfuse_data(
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    sample_size: int = 20
) -> dict[str, Any]:
    """验证 Langfuse 中的数据"""
    print(f"\n验证 Langfuse 数据 (采样 {sample_size} 条)")
    print("=" * 60)

    # 获取 traces
    traces_data = fetch_langfuse_traces(langfuse_host, public_key, secret_key, limit=sample_size)

    if not traces_data or "data" not in traces_data:
        print("❌ 无法获取 traces 数据")
        return {"valid": False, "errors": ["无法获取 traces 数据"]}

    traces = traces_data["data"]
    print(f"获取到 {len(traces)} 条 traces")

    errors = []
    warnings = []
    stats = {
        "total_traces": len(traces),
        "traces_with_metadata": 0,
        "traces_with_sessions": 0,
        "traces_with_user_id": 0,
        "traces_with_tags": 0,
        "observations_count": 0,
    }

    # 验证每条 trace
    for i, trace in enumerate(traces):
        trace_id = trace.get("id", "")

        # 检查 metadata
        if trace.get("metadata"):
            stats["traces_with_metadata"] += 1

        # 检查 session_id
        if trace.get("sessionId"):
            stats["traces_with_sessions"] += 1

        # 检查 user_id
        if trace.get("userId"):
            stats["traces_with_user_id"] += 1

        # 检查 tags
        if trace.get("tags"):
            stats["traces_with_tags"] += 1

        # 获取 observations
        if i < 5:  # 只检查前 5 条的 observations
            observations_data = fetch_langfuse_observations(langfuse_host, public_key, secret_key, trace_id)
            if observations_data and "data" in observations_data:
                stats["observations_count"] += len(observations_data["data"])

    # 输出统计
    print(f"\n数据统计:")
    print(f"  - 总 traces: {stats['total_traces']}")
    print(f"  - 有 metadata: {stats['traces_with_metadata']} ({stats['traces_with_metadata']/stats['total_traces']*100:.1f}%)")
    print(f"  - 有 session_id: {stats['traces_with_sessions']} ({stats['traces_with_sessions']/stats['total_traces']*100:.1f}%)")
    print(f"  - 有 user_id: {stats['traces_with_user_id']} ({stats['traces_with_user_id']/stats['total_traces']*100:.1f}%)")
    print(f"  - 有 tags: {stats['traces_with_tags']} ({stats['traces_with_tags']/stats['total_traces']*100:.1f}%)")
    print(f"  - observations 总数: {stats['observations_count']}")

    # 检查数据质量
    if stats["traces_with_metadata"] < stats["total_traces"] * 0.8:
        warnings.append(f"只有 {stats['traces_with_metadata']/stats['total_traces']*100:.1f}% 的 traces 有 metadata")

    if stats["traces_with_sessions"] < stats["total_traces"] * 0.8:
        warnings.append(f"只有 {stats['traces_with_sessions']/stats['total_traces']*100:.1f}% 的 traces 有 session_id")

    # 输出示例
    print(f"\n示例 traces:")
    for i, trace in enumerate(traces[:3]):
        print(f"\n  {i+1}. {trace.get('name', 'unknown')}")
        print(f"     ID: {trace.get('id', '')[:20]}...")
        print(f"     Session: {trace.get('sessionId', 'N/A')}")
        print(f"     User: {trace.get('userId', 'N/A')}")
        print(f"     Tags: {trace.get('tags', [])}")
        if trace.get("metadata"):
            print(f"     Metadata: {json.dumps(trace['metadata'], ensure_ascii=False)[:100]}...")

    return {
        "valid": len(errors) == 0,
        "stats": stats,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    """主函数"""
    print("=" * 60)
    print("Langfuse 数据验证工具")
    print("=" * 60)

    # 加载配置
    config = load_nacos_config(prod=True)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    lf_config = config.get("langfuse", {})

    if not lf_config.get("enabled"):
        print("❌ Langfuse 未启用", file=sys.stderr)
        sys.exit(1)

    # 验证数据
    result = validate_langfuse_data(
        langfuse_host=lf_config.get("host"),
        public_key=lf_config.get("public_key"),
        secret_key=lf_config.get("secret_key"),
        sample_size=20,
    )

    # 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)
    print(f"数据验证: {'✅ 通过' if result['valid'] else '❌ 失败'}")

    if result.get("warnings"):
        print(f"\n⚠️  警告:")
        for warning in result["warnings"]:
            print(f"  - {warning}")

    if result.get("errors"):
        print(f"\n❌ 错误:")
        for error in result["errors"]:
            print(f"  - {error}")

    print("\n✅ 数据验证完成")


if __name__ == "__main__":
    main()
