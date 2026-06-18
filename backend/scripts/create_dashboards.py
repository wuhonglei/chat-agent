#!/usr/bin/env python3
"""
通过 Langfuse tRPC API 创建 Dashboard 和 Widget。

用法:
    python3 create_dashboards.py --prod            # 创建所有 dashboard
    python3 create_dashboards.py --prod --dry-run  # 仅预览
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

import yaml

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
    config_path = os.path.abspath(NACOS_CONFIG_PATH)
    if not os.path.exists(config_path):
        print(f"ERROR: nacos config not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return cast(dict[str, Any], cfg) if isinstance(cfg, dict) else {}


_cfg = load_nacos_config()
_lf = _cfg.get("langfuse", {})

LANGFUSE_HOST = _lf.get("host", "")
LANGFUSE_PUBLIC_KEY = _lf.get("public_key", "")
LANGFUSE_SECRET_KEY = _lf.get("secret_key", "")

PROJECT_ID = "cmpwh4pcg0002qn07mv4f20af"  # chat-agent-prod


def trpc_call(procedure: str, payload: dict[str, Any], *, is_mutation: bool = False) -> dict[str, Any]:
    """调用 Langfuse tRPC endpoint。"""
    url = f"{LANGFUSE_HOST}/api/trpc/{procedure}"
    if not is_mutation:
        url += "?" + urllib.parse.urlencode({"batch": 1, "input": json.dumps({"0": payload})})

    headers = {
        "Content-Type": "application/json",
    }
    credentials = base64.b64encode(
        f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    headers["Authorization"] = f"Basic {credentials}"

    if is_mutation:
        data = json.dumps({"0": payload}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    else:
        req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            # tRPC batch response is an array
            if isinstance(result, list) and len(result) > 0:
                data = result[0].get("result", {}).get("data", {})
                return cast(dict[str, Any], data) if isinstance(data, dict) else {}
            return cast(dict[str, Any], result) if isinstance(result, dict) else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:500]}")
        return {"error": body}
    except Exception as e:
        return {"error": str(e)}


def create_widget(
    *,
    name: str,
    description: str,
    view: str,
    dimensions: list[dict[str, str]],
    metrics: list[dict[str, str]],
    filters: list[dict[str, Any]],
    chart_type: str,
    chart_config: dict[str, Any],
    min_version: int = 2,
) -> dict[str, Any]:
    """创建 Widget。"""
    payload = {
        "projectId": PROJECT_ID,
        "name": name,
        "description": description,
        "view": view,
        "dimensions": dimensions,
        "metrics": metrics,
        "filters": filters,
        "chartType": chart_type,
        "chartConfig": chart_config,
        "minVersion": min_version,
    }
    return trpc_call("dashboardWidgets.create", payload, is_mutation=True)


def create_dashboard(name: str, description: str) -> dict[str, Any]:
    """创建 Dashboard。"""
    payload = {
        "projectId": PROJECT_ID,
        "name": name,
        "description": description,
    }
    return trpc_call("dashboard.createDashboard", payload, is_mutation=True)


def update_dashboard_definition(dashboard_id: str, widgets: list[dict[str, Any]]) -> dict[str, Any]:
    """更新 Dashboard 定义（添加 widget 布局）。"""
    payload = {
        "projectId": PROJECT_ID,
        "dashboardId": dashboard_id,
        "definition": {"widgets": widgets},
    }
    return trpc_call("dashboard.updateDashboardDefinition", payload, is_mutation=True)


# ── Widget 定义 ──────────────────────────────────────────

TOOL_ANALYSIS_WIDGETS: list[dict[str, Any]] = [
    {
        "name": "工具调用次数分布",
        "description": "按 tool_name 统计工具调用次数",
        "view": "observations",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {"column": "type", "operator": "any of", "type": "stringOptions", "value": ["GENERATION", "SPAN", "TOOL"]}
        ],
        "chart_type": "HORIZONTAL_BAR",
        "chart_config": {"type": "HORIZONTAL_BAR", "row_limit": 20},
    },
    {
        "name": "工具调用趋势",
        "description": "按时间统计工具调用次数",
        "view": "observations",
        "dimensions": [],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {"column": "type", "operator": "any of", "type": "stringOptions", "value": ["GENERATION", "SPAN", "TOOL"]}
        ],
        "chart_type": "LINE_TIME_SERIES",
        "chart_config": {"type": "LINE_TIME_SERIES"},
    },
    {
        "name": "工具延迟分布",
        "description": "按 tool_name 统计 P95 延迟",
        "view": "observations",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "latency", "agg": "p95"}],
        "filters": [
            {"column": "type", "operator": "any of", "type": "stringOptions", "value": ["GENERATION", "SPAN", "TOOL"]}
        ],
        "chart_type": "HORIZONTAL_BAR",
        "chart_config": {"type": "HORIZONTAL_BAR", "row_limit": 20},
    },
    {
        "name": "模型调用延迟趋势",
        "description": "按模型统计 LLM 调用延迟趋势",
        "view": "observations",
        "dimensions": [{"field": "providedModelName"}],
        "metrics": [{"measure": "latency", "agg": "p95"}],
        "filters": [],
        "chart_type": "LINE_TIME_SERIES",
        "chart_config": {"type": "LINE_TIME_SERIES"},
    },
]

QUALITY_MONITORING_WIDGETS: list[dict[str, Any]] = [
    {
        "name": "用户反馈分布",
        "description": "like vs dislike 分布",
        "view": "scores-numeric",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {"column": "name", "operator": "any of", "type": "stringOptions", "value": ["user_feedback"]}
        ],
        "chart_type": "PIE",
        "chart_config": {"type": "PIE"},
    },
    {
        "name": "消息状态分布",
        "description": "done/stopped/failed 分布",
        "view": "scores-numeric",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {"column": "name", "operator": "any of", "type": "stringOptions", "value": ["message_status"]}
        ],
        "chart_type": "PIE",
        "chart_config": {"type": "PIE"},
    },
    {
        "name": "Token 用量趋势",
        "description": "按时间统计 token 消耗",
        "view": "observations",
        "dimensions": [],
        "metrics": [{"measure": "totalTokens", "agg": "sum"}],
        "filters": [],
        "chart_type": "LINE_TIME_SERIES",
        "chart_config": {"type": "LINE_TIME_SERIES"},
    },
    {
        "name": "Trace 延迟百分位",
        "description": "chat-turn 延迟 P50/P95/P99",
        "view": "traces",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "latency", "agg": "p50"}],
        "filters": [],
        "chart_type": "HORIZONTAL_BAR",
        "chart_config": {"type": "HORIZONTAL_BAR"},
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 Langfuse API 创建 Dashboard")
    parser.add_argument("--prod", action="store_true", help="使用 prod project")
    parser.add_argument("--dry-run", action="store_true", help="仅预览")
    args = parser.parse_args()

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("ERROR: Langfuse API keys not found in nacos config")
        sys.exit(1)

    if args.prod:
        global PROJECT_ID
        PROJECT_ID = "cmpwh4pcg0002qn07mv4f20af"

    print(f"Langfuse Host: {LANGFUSE_HOST}")
    print(f"Project ID: {PROJECT_ID}")
    print()

    # ── 创建工具分析 Dashboard ──
    print("=" * 60)
    print("Dashboard 1: 工具分析")
    print("=" * 60)

    if args.dry_run:
        print("  [DRY-RUN] Would create dashboard '工具分析'")
        for i, w in enumerate(TOOL_ANALYSIS_WIDGETS):
            print(f"  [DRY-RUN] Widget {i+1}: {w['name']}")
            print(f"    view={w['view']}, chart={w['chart_type']}")
            print(f"    dimensions={[d['field'] for d in w['dimensions']]}")
            print(f"    metrics=[{w['metrics'][0]['measure']}:{w['metrics'][0]['agg']}]")
    else:
        # 创建 dashboard
        result = create_dashboard("工具分析", "工具调用分析：次数分布、延迟分布、趋势")
        print(f"  Dashboard created: {json.dumps(result, indent=2, default=str)[:300]}")

        dashboard_id = result.get("id") or result.get("dashboard", {}).get("id")
        if not dashboard_id:
            print("  ERROR: Failed to get dashboard ID")
            return

        # 创建 widgets
        widget_placements = []
        for i, w in enumerate(TOOL_ANALYSIS_WIDGETS):
            print(f"  Creating widget: {w['name']}...")
            widget_result = create_widget(
                name=w["name"],
                description=w["description"],
                view=w["view"],
                dimensions=w["dimensions"],
                metrics=w["metrics"],
                filters=w["filters"],
                chart_type=w["chart_type"],
                chart_config=w["chart_config"],
            )
            widget_id = widget_result.get("widget", {}).get("id")
            if widget_id:
                widget_placements.append({
                    "type": "widget",
                    "id": f"placement-{i}",
                    "widgetId": widget_id,
                    "x": (i % 2) * 6,
                    "y": (i // 2) * 4,
                    "x_size": 6,
                    "y_size": 4,
                })
                print(f"    OK: {widget_id}")
            else:
                print(f"    FAILED: {json.dumps(widget_result, default=str)[:200]}")

        # 更新 dashboard definition
        if widget_placements:
            update_dashboard_definition(dashboard_id, widget_placements)
            print(f"  Dashboard updated with {len(widget_placements)} widgets")

    # ── 创建质量监控 Dashboard ──
    print()
    print("=" * 60)
    print("Dashboard 2: 质量监控")
    print("=" * 60)

    if args.dry_run:
        print("  [DRY-RUN] Would create dashboard '质量监控'")
        for i, w in enumerate(QUALITY_MONITORING_WIDGETS):
            print(f"  [DRY-RUN] Widget {i+1}: {w['name']}")
            print(f"    view={w['view']}, chart={w['chart_type']}")
            print(f"    dimensions={[d['field'] for d in w['dimensions']]}")
            print(f"    metrics=[{w['metrics'][0]['measure']}:{w['metrics'][0]['agg']}]")
    else:
        result = create_dashboard("质量监控", "质量监控：反馈分布、状态分布、Token 用量")
        print(f"  Dashboard created: {json.dumps(result, indent=2, default=str)[:300]}")

        dashboard_id = result.get("id") or result.get("dashboard", {}).get("id")
        if not dashboard_id:
            print("  ERROR: Failed to get dashboard ID")
            return

        widget_placements = []
        for i, w in enumerate(QUALITY_MONITORING_WIDGETS):
            print(f"  Creating widget: {w['name']}...")
            widget_result = create_widget(
                name=w["name"],
                description=w["description"],
                view=w["view"],
                dimensions=w["dimensions"],
                metrics=w["metrics"],
                filters=w["filters"],
                chart_type=w["chart_type"],
                chart_config=w["chart_config"],
            )
            widget_id = widget_result.get("widget", {}).get("id")
            if widget_id:
                widget_placements.append({
                    "type": "widget",
                    "id": f"placement-{i}",
                    "widgetId": widget_id,
                    "x": (i % 2) * 6,
                    "y": (i // 2) * 4,
                    "x_size": 6,
                    "y_size": 4,
                })
                print(f"    OK: {widget_id}")
            else:
                print(f"    FAILED: {json.dumps(widget_result, default=str)[:200]}")

        if widget_placements:
            update_dashboard_definition(dashboard_id, widget_placements)
            print(f"  Dashboard updated with {len(widget_placements)} widgets")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
