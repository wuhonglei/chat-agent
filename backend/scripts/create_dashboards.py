#!/usr/bin/env python3
"""
通过 Langfuse tRPC API 创建 Dashboard 和 Widget。

用法:
    python3 create_dashboards.py              # 使用 dev nacos 配置
    python3 create_dashboards.py --prod         # 使用 prod nacos 配置
    python3 create_dashboards.py --prod --dry-run  # 仅预览

    # 也可通过环境变量指定配置文件
    export NACOS_CONFIG=/path/to/ai-chat-prod@@DEFAULT_GROUP@@
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
from dataclasses import dataclass
from typing import Any, cast

import yaml

PROD_PROJECT_ID = "cmpwh4pcg0002qn07mv4f20af"  # chat-agent-prod
DEV_PROJECT_ID = "cmpwgw3qg0005t407qhqzomsg"  # chat-agent-dev

DEFAULT_PROJECT_IDS = {
    True: PROD_PROJECT_ID,
    False: DEV_PROJECT_ID,
}


@dataclass(frozen=True)
class LangfuseRuntime:
    host: str
    public_key: str
    secret_key: str
    project_id: str


# ── 从 nacos 配置文件读取 ──────────────────────────────
def _default_nacos_config_path(*, prod: bool) -> str:
    filename = (
        "ai-chat-prod@@DEFAULT_GROUP@@" if prod else "ai-chat-dev@@DEFAULT_GROUP@@"
    )
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
    config_path = resolve_nacos_config_path(prod=prod)
    if not os.path.exists(config_path):
        print(f"ERROR: nacos config not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return cast(dict[str, Any], cfg) if isinstance(cfg, dict) else {}


def load_langfuse_runtime(*, prod: bool) -> LangfuseRuntime:
    cfg = load_nacos_config(prod=prod)
    lf = cfg.get("langfuse", {})

    # 环境变量优先覆盖（nacos 中 key 可能截断）
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY") or lf.get("public_key", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY") or lf.get("secret_key", "")
    project_id = lf.get("project_id") or DEFAULT_PROJECT_IDS[prod]
    if not project_id:
        print("ERROR: nacos 配置中缺少 langfuse.project_id")
        sys.exit(1)

    return LangfuseRuntime(
        host=lf.get("host", ""),
        public_key=public_key,
        secret_key=secret_key,
        project_id=str(project_id),
    )


def trpc_call(
    langfuse: LangfuseRuntime,
    procedure: str,
    payload: dict[str, Any],
    *,
    is_mutation: bool = False,
) -> dict[str, Any]:
    """调用 Langfuse tRPC endpoint。"""
    url = f"{langfuse.host}/api/trpc/{procedure}"
    if not is_mutation:
        url += "?" + urllib.parse.urlencode(
            {"batch": 1, "input": json.dumps({"0": payload})}
        )

    headers = {
        "Content-Type": "application/json",
    }
    credentials = base64.b64encode(
        f"{langfuse.public_key}:{langfuse.secret_key}".encode()
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
    langfuse: LangfuseRuntime,
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
        "projectId": langfuse.project_id,
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
    return trpc_call(langfuse, "dashboardWidgets.create", payload, is_mutation=True)


def create_dashboard(
    langfuse: LangfuseRuntime, name: str, description: str
) -> dict[str, Any]:
    """创建 Dashboard。"""
    payload = {
        "projectId": langfuse.project_id,
        "name": name,
        "description": description,
    }
    return trpc_call(langfuse, "dashboard.createDashboard", payload, is_mutation=True)


def update_dashboard_definition(
    langfuse: LangfuseRuntime,
    dashboard_id: str,
    widgets: list[dict[str, Any]],
) -> dict[str, Any]:
    """更新 Dashboard 定义（添加 widget 布局）。"""
    payload = {
        "projectId": langfuse.project_id,
        "dashboardId": dashboard_id,
        "definition": {"widgets": widgets},
    }
    return trpc_call(
        langfuse, "dashboard.updateDashboardDefinition", payload, is_mutation=True
    )


# ── Widget 定义 ──────────────────────────────────────────

TOOL_ANALYSIS_WIDGETS: list[dict[str, Any]] = [
    {
        "name": "工具调用次数分布",
        "description": "按 tool_name 统计工具调用次数",
        "view": "observations",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {
                "column": "type",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["GENERATION", "SPAN", "TOOL"],
            }
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
            {
                "column": "type",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["GENERATION", "SPAN", "TOOL"],
            }
        ],
        "chart_type": "LINE_TIME_SERIES",
        "chart_config": {"type": "LINE_TIME_SERIES"},
    },
    {
        "name": "工具调用趋势（Server 维度）",
        "description": "按 MCP Server 分组的工具调用次数趋势",
        "view": "observations",
        "dimensions": [{"field": "metadata.server_name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {
                "column": "type",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["GENERATION", "SPAN", "TOOL"],
            }
        ],
        "chart_type": "LINE_TIME_SERIES",
        "chart_config": {"type": "LINE_TIME_SERIES"},
    },
    {
        "name": "工具调用趋势（Tool 维度）",
        "description": "按具体工具名称分组的工具调用次数趋势",
        "view": "observations",
        "dimensions": [{"field": "metadata.tool_name"}],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": [
            {
                "column": "type",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["GENERATION", "SPAN", "TOOL"],
            }
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
            {
                "column": "type",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["GENERATION", "SPAN", "TOOL"],
            }
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
            {
                "column": "name",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["user_feedback"],
            }
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
            {
                "column": "name",
                "operator": "any of",
                "type": "stringOptions",
                "value": ["message_status"],
            }
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
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用 ai-chat-prod nacos 配置（默认 ai-chat-dev）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预览")
    args = parser.parse_args()

    config_path = resolve_nacos_config_path(prod=args.prod)
    print(f"Using nacos config: {config_path}")

    langfuse = load_langfuse_runtime(prod=args.prod)

    if not langfuse.public_key or not langfuse.secret_key:
        print("ERROR: nacos 配置中缺少 langfuse.public_key / langfuse.secret_key")
        sys.exit(1)

    print(f"Langfuse Host: {langfuse.host}")
    print(f"Project ID: {langfuse.project_id}")
    print()

    # ── 创建工具分析 Dashboard ──
    print("=" * 60)
    print("Dashboard 1: 工具分析")
    print("=" * 60)

    if args.dry_run:
        print("  [DRY-RUN] Would create dashboard '工具分析'")
        for i, w in enumerate(TOOL_ANALYSIS_WIDGETS):
            print(f"  [DRY-RUN] Widget {i + 1}: {w['name']}")
            print(f"    view={w['view']}, chart={w['chart_type']}")
            print(f"    dimensions={[d['field'] for d in w['dimensions']]}")
            print(
                f"    metrics=[{w['metrics'][0]['measure']}:{w['metrics'][0]['agg']}]"
            )
    else:
        # 创建 dashboard
        result = create_dashboard(
            langfuse, "工具分析", "工具调用分析：次数分布、延迟分布、趋势"
        )
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
                langfuse,
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
                widget_placements.append(
                    {
                        "type": "widget",
                        "id": f"placement-{i}",
                        "widgetId": widget_id,
                        "x": (i % 2) * 6,
                        "y": (i // 2) * 4,
                        "x_size": 6,
                        "y_size": 4,
                    }
                )
                print(f"    OK: {widget_id}")
            else:
                print(f"    FAILED: {json.dumps(widget_result, default=str)[:200]}")

        # 更新 dashboard definition
        if widget_placements:
            update_dashboard_definition(langfuse, dashboard_id, widget_placements)
            print(f"  Dashboard updated with {len(widget_placements)} widgets")

    # ── 创建质量监控 Dashboard ──
    print()
    print("=" * 60)
    print("Dashboard 2: 质量监控")
    print("=" * 60)

    if args.dry_run:
        print("  [DRY-RUN] Would create dashboard '质量监控'")
        for i, w in enumerate(QUALITY_MONITORING_WIDGETS):
            print(f"  [DRY-RUN] Widget {i + 1}: {w['name']}")
            print(f"    view={w['view']}, chart={w['chart_type']}")
            print(f"    dimensions={[d['field'] for d in w['dimensions']]}")
            print(
                f"    metrics=[{w['metrics'][0]['measure']}:{w['metrics'][0]['agg']}]"
            )
    else:
        result = create_dashboard(
            langfuse, "质量监控", "质量监控：反馈分布、状态分布、Token 用量"
        )
        print(f"  Dashboard created: {json.dumps(result, indent=2, default=str)[:300]}")

        dashboard_id = result.get("id") or result.get("dashboard", {}).get("id")
        if not dashboard_id:
            print("  ERROR: Failed to get dashboard ID")
            return

        widget_placements = []
        for i, w in enumerate(QUALITY_MONITORING_WIDGETS):
            print(f"  Creating widget: {w['name']}...")
            widget_result = create_widget(
                langfuse,
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
                widget_placements.append(
                    {
                        "type": "widget",
                        "id": f"placement-{i}",
                        "widgetId": widget_id,
                        "x": (i % 2) * 6,
                        "y": (i // 2) * 4,
                        "x_size": 6,
                        "y_size": 4,
                    }
                )
                print(f"    OK: {widget_id}")
            else:
                print(f"    FAILED: {json.dumps(widget_result, default=str)[:200]}")

        if widget_placements:
            update_dashboard_definition(langfuse, dashboard_id, widget_placements)
            print(f"  Dashboard updated with {len(widget_placements)} widgets")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
