"""Static MCP registry and frontend-facing config."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.core.config import settings
from app.mcp.mcp_servers.code_exec_mcp.server import mcp as code_exec_mcp
from app.mcp.mcp_servers.ip_locator_mcp.server import mcp as ip_locator_mcp
from app.mcp.mcp_servers.tavily_mcp.server import mcp as tavily_mcp
from app.mcp.mcp_servers.time_mcp.server import mcp as time_mcp
from app.mcp.mcp_servers.weather_mcp.server import mcp as weather_mcp
from app.schemas.mcp import MCPConfigForFeDict


class MCPRegistry:
    """Hold static server registrations and FE metadata."""

    def __init__(self) -> None:
        self._servers: dict[str, Any] = {
            "ip-locator-mcp": ip_locator_mcp,
            "time-mcp": time_mcp,
            "context7-mcp": settings.mcp.context7_mcp.model_dump(
                mode="json", exclude={"cache_config"}
            ),
            "weather-mcp": weather_mcp,
            "tavily-mcp": tavily_mcp,
            "code-exec-mcp": code_exec_mcp,
        }
        self._fe_configs: list[MCPConfigForFeDict] = [
            {
                "id": "context7-mcp",
                "name": "Context7",
                "icon": "https://context7.com/favicon.ico",
                "description": "为 LLM 和 AI 代码编辑器提供最新文档",
                "online": False,
            },
            {
                "id": "weather-mcp",
                "name": "天气查询",
                "icon": "https://www.qweather.com/favicon.ico",
                "description": "天气信息查询",
                "online": False,
            },
            {
                "id": "tavily-mcp",
                "name": "联网搜索",
                "icon": "https://docs.tavily.com/mintlify-assets/_mintlify/favicons/tavilyai/SXaxSfweEU3ftIlh/_generated/favicon/apple-touch-icon.png",
                "description": "联网搜索和内容提取",
                "online": False,
            },
            {
                "id": "code-exec-mcp",
                "name": "代码执行",
                "icon": "https://github.com/alibaba/OpenSandbox/raw/main/docs/assets/logo.svg",
                "description": "安全的代码执行服务，使用沙箱隔离确保安全性",
                "online": False,
            },
        ]

    def get_servers(self) -> dict[str, Any]:
        return dict(self._servers)

    def get_fe_configs(self) -> list[MCPConfigForFeDict]:
        return [self._clone_fe_config(config) for config in self._fe_configs]

    @staticmethod
    def _clone_fe_config(config: MCPConfigForFeDict) -> MCPConfigForFeDict:
        return {
            "id": config["id"],
            "name": config["name"],
            "icon": config["icon"],
            "description": config["description"],
            "online": config["online"],
        }


def is_local_fastmcp(server_instance: Any) -> bool:
    return isinstance(server_instance, FastMCP)
