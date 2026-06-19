#!/usr/bin/env python3
"""
Langfuse 深度分析脚本
分析 traces 和 observations 的详细数据
"""

import json
import os
import sys
import statistics
from typing import Any, Optional
from collections import Counter, defaultdict
from datetime import datetime

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
        url = f"{langfuse_host}/api/public/traces?userId={user_id}&limit={limit}&page={page}"
        req = urllib.request.Request(url)
        credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        req.add_header("Authorization", f"Basic {credentials}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                traces = data.get("data", [])

                if not traces:
                    break

                all_traces.extend(traces)

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
        return []


def analyze_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """分析 observations 数据"""
    if not observations:
        return {}

    # 分类统计
    generations = []
    spans = []
    tool_calls = []

    for obs in observations:
        obs_type = obs.get("type", "")

        if obs_type == "GENERATION":
            generations.append(obs)
        elif obs_type == "SPAN":
            spans.append(obs)

        # 检查是否是工具调用
        name = obs.get("name", "")
        if "tool" in name.lower() or "mcp" in name.lower():
            tool_calls.append(obs)

    # 分析 generations
    generation_stats = {}
    if generations:
        latencies = []
        models = []
        input_tokens = []
        output_tokens = []

        for gen in generations:
            # 计算延迟
            start_time = gen.get("startTime")
            end_time = gen.get("endTime")
            if start_time and end_time:
                try:
                    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    latency = (end - start).total_seconds() * 1000
                    latencies.append(latency)
                except:
                    pass

            # 模型
            model = gen.get("model")
            if model:
                models.append(model)

            # Token 使用
            usage = gen.get("usage", {})
            if usage:
                input_tokens.append(usage.get("inputTokens", 0))
                output_tokens.append(usage.get("outputTokens", 0))

        generation_stats = {
            "count": len(generations),
            "latency": {
                "mean": statistics.mean(latencies) if latencies else 0,
                "median": statistics.median(latencies) if latencies else 0,
                "min": min(latencies) if latencies else 0,
                "max": max(latencies) if latencies else 0,
                "p90": sorted(latencies)[int(len(latencies) * 0.9)] if len(latencies) >= 10 else max(latencies) if latencies else 0,
            },
            "models": dict(Counter(models).most_common()),
            "tokens": {
                "input_total": sum(input_tokens),
                "output_total": sum(output_tokens),
                "input_mean": statistics.mean(input_tokens) if input_tokens else 0,
                "output_mean": statistics.mean(output_tokens) if output_tokens else 0,
            },
        }

    # 分析 spans
    span_stats = {}
    if spans:
        span_latencies = []
        span_names = []

        for span in spans:
            start_time = span.get("startTime")
            end_time = span.get("endTime")
            if start_time and end_time:
                try:
                    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    latency = (end - start).total_seconds() * 1000
                    span_latencies.append(latency)
                except:
                    pass

            name = span.get("name", "")
            if name:
                span_names.append(name)

        span_stats = {
            "count": len(spans),
            "latency": {
                "mean": statistics.mean(span_latencies) if span_latencies else 0,
                "median": statistics.median(span_latencies) if span_latencies else 0,
                "min": min(span_latencies) if span_latencies else 0,
                "max": max(span_latencies) if span_latencies else 0,
            },
            "names": dict(Counter(span_names).most_common(10)),
        }

    # 分析工具调用
    tool_stats = {}
    if tool_calls:
        tool_latencies = []
        tool_names = []

        for tool in tool_calls:
            start_time = tool.get("startTime")
            end_time = tool.get("endTime")
            if start_time and end_time:
                try:
                    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    latency = (end - start).total_seconds() * 1000
                    tool_latencies.append(latency)
                except:
                    pass

            name = tool.get("name", "")
            if name:
                tool_names.append(name)

        tool_stats = {
            "count": len(tool_calls),
            "latency": {
                "mean": statistics.mean(tool_latencies) if tool_latencies else 0,
                "median": statistics.median(tool_latencies) if tool_latencies else 0,
                "min": min(tool_latencies) if tool_latencies else 0,
                "max": max(tool_latencies) if tool_latencies else 0,
            },
            "names": dict(Counter(tool_names).most_common(10)),
        }

    return {
        "generations": generation_stats,
        "spans": span_stats,
        "tool_calls": tool_stats,
    }


def generate_deep_report(
    traces: list[dict[str, Any]],
    observations_by_trace: dict[str, list[dict[str, Any]]],
    user_id: str,
) -> str:
    """生成深度分析报告"""
    report = []
    report.append("=" * 80)
    report.append("Langfuse 深度分析报告")
    report.append(f"用户 ID: {user_id}")
    report.append("=" * 80)

    # 基本统计
    report.append(f"\n📊 基本统计")
    report.append("-" * 60)
    report.append(f"总 Trace 数: {len(traces)}")
    report.append(f"有 Observations 的 Trace: {len(observations_by_trace)}")

    # 收集所有 observations
    all_observations = []
    for obs_list in observations_by_trace.values():
        all_observations.extend(obs_list)

    report.append(f"总 Observation 数: {len(all_observations)}")

    # 分析 observations
    obs_analysis = analyze_observations(all_observations)

    # Generation 分析
    gen_stats = obs_analysis.get("generations", {})
    if gen_stats:
        report.append(f"\n🤖 Generation 分析")
        report.append("-" * 60)
        report.append(f"Generation 数量: {gen_stats.get('count', 0)}")

        latency = gen_stats.get("latency", {})
        if latency:
            report.append(f"\n⏱️  Generation 延迟:")
            report.append(f"  平均: {latency.get('mean', 0):.2f} ms")
            report.append(f"  中位数: {latency.get('median', 0):.2f} ms")
            report.append(f"  最小: {latency.get('min', 0):.2f} ms")
            report.append(f"  最大: {latency.get('max', 0):.2f} ms")
            report.append(f"  P90: {latency.get('p90', 0):.2f} ms")

        models = gen_stats.get("models", {})
        if models:
            report.append(f"\n📦 使用的模型:")
            for model, count in models.items():
                report.append(f"  {model}: {count} 次")

        tokens = gen_stats.get("tokens", {})
        if tokens:
            report.append(f"\n🎫 Token 使用:")
            report.append(f"  输入 Token 总数: {tokens.get('input_total', 0)}")
            report.append(f"  输出 Token 总数: {tokens.get('output_total', 0)}")
            report.append(f"  平均输入 Token: {tokens.get('input_mean', 0):.0f}")
            report.append(f"  平均输出 Token: {tokens.get('output_mean', 0):.0f}")

    # Span 分析
    span_stats = obs_analysis.get("spans", {})
    if span_stats:
        report.append(f"\n📏 Span 分析")
        report.append("-" * 60)
        report.append(f"Span 数量: {span_stats.get('count', 0)}")

        latency = span_stats.get("latency", {})
        if latency:
            report.append(f"\n⏱️  Span 延迟:")
            report.append(f"  平均: {latency.get('mean', 0):.2f} ms")
            report.append(f"  中位数: {latency.get('median', 0):.2f} ms")
            report.append(f"  最小: {latency.get('min', 0):.2f} ms")
            report.append(f"  最大: {latency.get('max', 0):.2f} ms")

        names = span_stats.get("names", {})
        if names:
            report.append(f"\n📝 Span 名称分布:")
            for name, count in names.items():
                report.append(f"  {name}: {count} 次")

    # 工具调用分析
    tool_stats = obs_analysis.get("tool_calls", {})
    if tool_stats:
        report.append(f"\n🔧 工具调用分析")
        report.append("-" * 60)
        report.append(f"工具调用数量: {tool_stats.get('count', 0)}")

        latency = tool_stats.get("latency", {})
        if latency:
            report.append(f"\n⏱️  工具调用延迟:")
            report.append(f"  平均: {latency.get('mean', 0):.2f} ms")
            report.append(f"  中位数: {latency.get('median', 0):.2f} ms")
            report.append(f"  最小: {latency.get('min', 0):.2f} ms")
            report.append(f"  最大: {latency.get('max', 0):.2f} ms")

        names = tool_stats.get("names", {})
        if names:
            report.append(f"\n🛠️  工具名称分布:")
            for name, count in names.items():
                report.append(f"  {name}: {count} 次")
    else:
        report.append(f"\n🔧 工具调用分析")
        report.append("-" * 60)
        report.append(f"未发现工具调用")

    # 性能建议
    report.append(f"\n💡 性能分析与建议")
    report.append("-" * 60)

    if gen_stats:
        avg_latency = gen_stats.get("latency", {}).get("mean", 0)
        if avg_latency > 5000:
            report.append(f"⚠️  平均 Generation 延迟较高 ({avg_latency:.0f}ms)")
            report.append(f"   建议: 优化模型调用或使用更快的模型")
        elif avg_latency > 2000:
            report.append(f"⚠️  平均 Generation 延迟中等 ({avg_latency:.0f}ms)")
            report.append(f"   建议: 可以进一步优化")
        else:
            report.append(f"✅ 平均 Generation 延迟良好 ({avg_latency:.0f}ms)")

    if tool_stats:
        tool_count = tool_stats.get("count", 0)
        if tool_count > 0:
            avg_tool_latency = tool_stats.get("latency", {}).get("mean", 0)
            if avg_tool_latency > 3000:
                report.append(f"⚠️  平均工具调用延迟较高 ({avg_tool_latency:.0f}ms)")
                report.append(f"   建议: 优化工具执行或添加缓存")
            else:
                report.append(f"✅ 平均工具调用延迟良好 ({avg_tool_latency:.0f}ms)")

    report.append("\n" + "=" * 80)

    return "\n".join(report)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Langfuse 深度分析")
    parser.add_argument(
        "--user-id",
        default="ad64eb0e-9012-4b61-94b1-8709dea29d68",
        help="用户 ID (默认: ad64eb0e-9012-4b61-94b1-8709dea29d68)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="分析的 trace 数量限制 (默认: 50)"
    )
    parser.add_argument(
        "--output",
        default="scripts/langfuse_deep_analysis.json",
        help="输出文件路径"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Langfuse 深度分析工具")
    print("=" * 60)
    print(f"用户 ID: {args.user_id}")
    print(f"限制: {args.limit} 条 traces")
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

    host = lf_config.get("host")
    public_key = lf_config.get("public_key")
    secret_key = lf_config.get("secret_key")

    # 获取 traces
    print(f"\n正在获取用户 {args.user_id} 的 traces...")
    traces = fetch_langfuse_traces(
        langfuse_host=host,
        public_key=public_key,
        secret_key=secret_key,
        user_id=args.user_id,
        limit=args.limit,
    )

    print(f"获取到 {len(traces)} 条 traces")

    if not traces:
        print("❌ 没有找到数据", file=sys.stderr)
        return

    # 获取 observations
    print(f"\n正在获取 observations...")
    observations_by_trace = {}

    for i, trace in enumerate(traces[:args.limit], 1):
        trace_id = trace.get("id")
        if trace_id:
            obs = fetch_trace_observations(host, public_key, secret_key, trace_id)
            if obs:
                observations_by_trace[trace_id] = obs

            if i % 10 == 0:
                print(f"  已处理 {i}/{min(len(traces), args.limit)} 条 traces")

    print(f"获取到 {len(observations_by_trace)} 条有 observations 的 traces")

    # 生成报告
    print(f"\n正在生成分析报告...")
    report = generate_deep_report(traces, observations_by_trace, args.user_id)
    print(report)

    # 保存结果
    output_data = {
        "user_id": args.user_id,
        "analysis_time": datetime.now().isoformat(),
        "total_traces": len(traces),
        "traces_with_observations": len(observations_by_trace),
        "traces_sample": traces[:5],
        "observations_sample": {k: v[:2] for k, v in list(observations_by_trace.items())[:5]},
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 深度分析结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
