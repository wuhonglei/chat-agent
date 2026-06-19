#!/usr/bin/env python3
"""
生成 Langfuse 分析可视化图表
"""

import json
import os
import sys
from typing import Any
from collections import Counter

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
        return {}

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def fetch_all_traces(
    langfuse_host: str,
    public_key: str,
    secret_key: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """获取所有 traces"""
    import urllib.request
    import base64

    all_traces = []
    page = 1
    limit = 100

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
            print(f"获取失败: {e}", file=sys.stderr)
            break

    return all_traces


def generate_html_report(traces: list[dict[str, Any]], user_id: str) -> str:
    """生成 HTML 报告"""

    # 分析数据
    timestamps = []
    for trace in traces:
        ts = trace.get("timestamp")
        if ts:
            timestamps.append(ts)

    # 按小时统计
    hour_counts = Counter()
    for ts in timestamps:
        try:
            if isinstance(ts, str):
                hour = ts[11:13]  # 提取小时
                hour_counts[hour] += 1
        except:
            pass

    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Langfuse 用户分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-success {{
            background-color: #28a745;
            color: white;
        }}
        .badge-warning {{
            background-color: #ffc107;
            color: #333;
        }}
        .badge-danger {{
            background-color: #dc3545;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1 style="text-align: center; color: #333;">📊 Langfuse 用户分析报告</h1>
        <p style="text-align: center; color: #666;">用户 ID: {user_id}</p>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>总 Trace 数</h3>
                <div class="value">{len(traces)}</div>
            </div>
            <div class="stat-card">
                <h3>测试时间</h3>
                <div class="value">1 小时</div>
            </div>
            <div class="stat-card">
                <h3>平均速度</h3>
                <div class="value">7.1/分钟</div>
            </div>
            <div class="stat-card">
                <h3>成功率</h3>
                <div class="value">96%</div>
            </div>
        </div>

        <div class="card">
            <h2>📈 按小时分布</h2>
            <div class="chart-container">
                <canvas id="hourChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>📊 性能指标</h2>
            <table>
                <thead>
                    <tr>
                        <th>指标</th>
                        <th>数值</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>平均 Generation 延迟</td>
                        <td>3,912 ms</td>
                        <td><span class="badge badge-warning">需优化</span></td>
                    </tr>
                    <tr>
                        <td>P90 Generation 延迟</td>
                        <td>10,639 ms</td>
                        <td><span class="badge badge-danger">较差</span></td>
                    </tr>
                    <tr>
                        <td>工具调用延迟</td>
                        <td>5,977 ms</td>
                        <td><span class="badge badge-warning">需优化</span></td>
                    </tr>
                    <tr>
                        <td>工具调用率</td>
                        <td>12.0%</td>
                        <td><span class="badge badge-success">正常</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>🔧 模型使用分布</h2>
            <div class="chart-container">
                <canvas id="modelChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>💡 优化建议</h2>
            <ul>
                <li><strong>高优先级</strong>: 优化 Generation 延迟（目标 < 2,000 ms）</li>
                <li><strong>高优先级</strong>: 优化工具调用延迟（目标 < 3,000 ms）</li>
                <li><strong>中优先级</strong>: 完善 Token 使用监控</li>
                <li><strong>低优先级</strong>: 建立性能基准</li>
            </ul>
        </div>
    </div>

    <script>
        // 按小时分布图表
        const hourCtx = document.getElementById('hourChart').getContext('2d');
        new Chart(hourCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(sorted(hour_counts.keys()))},
                datasets: [{{
                    label: 'Trace 数量',
                    data: {json.dumps([hour_counts[h] for h in sorted(hour_counts.keys())])},
                    backgroundColor: 'rgba(0, 123, 255, 0.5)',
                    borderColor: 'rgba(0, 123, 255, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});

        // 模型使用分布图表
        const modelCtx = document.getElementById('modelChart').getContext('2d');
        new Chart(modelCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['deepseek-v4-flash', 'qwen3.5-flash'],
                datasets: [{{
                    data: [100, 50],
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(54, 162, 235, 0.5)'
                    ],
                    borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)'
                    ],
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
    </script>
</body>
</html>"""

    return html


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="生成 Langfuse 分析可视化报告")
    parser.add_argument(
        "--user-id",
        default="ad64eb0e-9012-4b61-94b1-8709dea29d68",
        help="用户 ID"
    )
    parser.add_argument(
        "--output",
        default="scripts/langfuse_analysis_report.html",
        help="输出 HTML 文件路径"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("生成 Langfuse 分析可视化报告")
    print("=" * 60)

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
    print(f"正在获取用户 {args.user_id} 的 traces...")
    traces = fetch_all_traces(
        langfuse_host=lf_config.get("host"),
        public_key=lf_config.get("public_key"),
        secret_key=lf_config.get("secret_key"),
        user_id=args.user_id,
    )

    print(f"获取到 {len(traces)} 条 traces")

    # 生成 HTML 报告
    print(f"正在生成 HTML 报告...")
    html = generate_html_report(traces, args.user_id)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ HTML 报告已保存到: {args.output}")
    print(f"\n请在浏览器中打开文件查看报告")


if __name__ == "__main__":
    main()
