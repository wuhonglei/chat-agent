#!/usr/bin/env python3
"""
分析 Langfuse 中指定用户的数据
"""

import json
import os
import sys
import statistics
from typing import Any, Optional
from collections import Counter, defaultdict

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
    user_id: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """从 Langfuse 获取指定用户的 traces"""
    import urllib.request
    import base64

    all_traces = []
    page = 1

    while True:
        # 使用正确的参数格式
        url = f"{langfuse_host}/api/public/traces?limit={limit}&page={page}"
        req = urllib.request.Request(url)
        credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        req.add_header("Authorization", f"Basic {credentials}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                traces = data.get("data", [])

                if not traces:
                    break

                # 过滤指定用户的 traces
                user_traces = [t for t in traces if t.get("userId") == user_id]
                all_traces.extend(user_traces)

                # 检查是否还有更多数据
                if len(traces) < limit:
                    break

                page += 1
        except Exception as e:
            print(f"❌ 获取 traces 失败: {e}", file=sys.stderr)
            break

    return all_traces


def fetch_trace_observations(
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    trace_id: str,
) -> list[dict[str, Any]]:
    """获取 trace 的 observations"""
    import urllib.request
    import base64

    url = f"{langfuse_host}/api/public/observations?traceId={trace_id}"
    req = urllib.request.Request(url)
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", [])
    except Exception as e:
        print(f"❌ 获取 observations 失败: {e}", file=sys.stderr)
        return []


def analyze_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """分析 traces 数据"""
    if not traces:
        return {}

    # 基本统计
    total_traces = len(traces)

    # 提取元数据
    response_times = []
    tool_calls_counts = []
    tool_names = []
    server_names = []
    interaction_patterns = []

    for trace in traces:
        metadata = trace.get("metadata", {})

        # 响应时间
        if "response_time_ms" in metadata:
            response_times.append(metadata["response_time_ms"])

        # 工具调用
        tool_calls_count = metadata.get("tool_calls_count", 0)
        tool_calls_counts.append(tool_calls_count)

        # 工具名称
        if "tool_names" in metadata:
            tool_names.extend(metadata["tool_names"])

        # 服务器名称
        if "server_names" in metadata:
            server_names.extend(metadata["server_names"])

        # 交互模式
        if "interaction_pattern" in metadata:
            interaction_patterns.append(metadata["interaction_pattern"])

    # 计算延迟统计
    latency_stats = {}
    if response_times:
        latency_stats = {
            "count": len(response_times),
            "mean": statistics.mean(response_times),
            "median": statistics.median(response_times),
            "min": min(response_times),
            "max": max(response_times),
            "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0,
            "p90": sorted(response_times)[int(len(response_times) * 0.9)] if len(response_times) >= 10 else max(response_times),
            "p95": sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) >= 20 else max(response_times),
        }

    # 工具调用统计
    tool_calls_stats = {
        "total_tool_calls": sum(tool_calls_counts),
        "avg_tool_calls_per_trace": statistics.mean(tool_calls_counts) if tool_calls_counts else 0,
        "traces_with_tool_calls": sum(1 for c in tool_calls_counts if c > 0),
        "traces_without_tool_calls": sum(1 for c in tool_calls_counts if c == 0),
    }

    # 工具使用频率
    tool_usage = Counter(tool_names)
    server_usage = Counter(server_names)

    # 交互模式分布
    pattern_distribution = Counter(interaction_patterns)

    return {
        "total_traces": total_traces,
        "latency_stats": latency_stats,
        "tool_calls_stats": tool_calls_stats,
        "tool_usage": dict(tool_usage.most_common(20)),
        "server_usage": dict(server_usage.most_common(10)),
        "pattern_distribution": dict(pattern_distribution.most_common()),
    }


def generate_report(analysis: dict[str, Any], user_id: str) -> str:
    """生成分析报告"""
    report = []
    report.append("=" * 70)
    report.append(f"Langfuse 用户数据分析报告")
    report.append(f"用户 ID: {user_id}")
    report.append("=" * 70)

    # 基本统计
    report.append(f"\n📊 基本统计")
    report.append("-" * 40)
    report.append(f"总 Trace 数: {analysis.get('total_traces', 0)}")

    # 延迟统计
    latency = analysis.get("latency_stats", {})
    if latency:
        report.append(f"\n⏱️  延迟统计")
        report.append("-" * 40)
        report.append(f"样本数: {latency.get('count', 0)}")
        report.append(f"平均延迟: {latency.get('mean', 0):.2f} ms")
        report.append(f"中位数延迟: {latency.get('median', 0):.2f} ms")
        report.append(f"最小延迟: {latency.get('min', 0):.2f} ms")
        report.append(f"最大延迟: {latency.get('max', 0):.2f} ms")
        report.append(f"标准差: {latency.get('stdev', 0):.2f} ms")
        report.append(f"P90 延迟: {latency.get('p90', 0):.2f} ms")
        report.append(f"P95 延迟: {latency.get('p95', 0):.2f} ms")

    # 工具调用统计
    tool_calls = analysis.get("tool_calls_stats", {})
    if tool_calls:
        report.append(f"\n🔧 工具调用统计")
        report.append("-" * 40)
        report.append(f"总工具调用次数: {tool_calls.get('total_tool_calls', 0)}")
        report.append(f"平均工具调用/Trace: {tool_calls.get('avg_tool_calls_per_trace', 0):.2f}")
        report.append(f"有工具调用的 Trace: {tool_calls.get('traces_with_tool_calls', 0)}")
        report.append(f"无工具调用的 Trace: {tool_calls.get('traces_without_tool_calls', 0)}")

    # 工具使用频率
    tool_usage = analysis.get("tool_usage", {})
    if tool_usage:
        report.append(f"\n🛠️  工具使用频率 (Top 10)")
        report.append("-" * 40)
        for tool_name, count in list(tool_usage.items())[:10]:
            report.append(f"  {tool_name:<30} {count:>4} 次")

    # 服务器使用频率
    server_usage = analysis.get("server_usage", {})
    if server_usage:
        report.append(f"\n🖥️  MCP Server 使用频率")
        report.append("-" * 40)
        for server_name, count in server_usage.items():
            report.append(f"  {server_name:<20} {count:>4} 次")

    # 交互模式分布
    patterns = analysis.get("pattern_distribution", {})
    if patterns:
        report.append(f"\n📈 交互模式分布")
        report.append("-" * 40)
        for pattern, count in patterns.items():
            report.append(f"  {pattern:<20} {count:>4} 次")

    report.append("\n" + "=" * 70)

    return "\n".join(report)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="分析 Langfuse 中指定用户的数据")
    parser.add_argument(
        "--user-id",
        default="ad64eb0e-9012-4b61-94b1-8709dea29d68",
        help="用户 ID (默认: ad64eb0e-9012-4b61-94b1-8709dea29d68)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="最大获取数量 (默认: 1000)"
    )
    parser.add_argument(
        "--output",
        default="scripts/langfuse_user_analysis.json",
        help="输出文件路径"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Langfuse 用户数据分析工具")
    print("=" * 60)
    print(f"用户 ID: {args.user_id}")
    print(f"限制: {args.limit}")
    print(f"输出文件: {args.output}")

    # 加载配置
    config = load_nacos_config(prod=args.prod)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    lf_config = config.get("langfuse", {})

    if not lf_config.get("enabled"):
        print("❌ Langfuse 未启用", file=sys.stderr)
        sys.exit(1)

    # 获取 traces
    print(f"\n正在获取用户 {args.user_id} 的 traces...")
    traces = fetch_langfuse_traces(
        langfuse_host=lf_config.get("host"),
        public_key=lf_config.get("public_key"),
        secret_key=lf_config.get("secret_key"),
        user_id=args.user_id,
        limit=args.limit,
    )

    print(f"获取到 {len(traces)} 条 traces")

    if not traces:
        print("❌ 没有找到数据", file=sys.stderr)
        return

    # 分析数据
    print(f"\n正在分析数据...")
    analysis = analyze_traces(traces)

    # 生成报告
    report = generate_report(analysis, args.user_id)
    print(report)

    # 保存结果
    output_data = {
        "user_id": args.user_id,
        "total_traces": len(traces),
        "analysis": analysis,
        "traces_sample": traces[:10],  # 保存前 10 条作为示例
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
