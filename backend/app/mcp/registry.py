"""Static MCP registry."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.mcp.mcp_servers.code_exec_mcp.server import mcp as code_exec_mcp
from app.mcp.mcp_servers.file_mcp.server import mcp as file_mcp
from app.mcp.mcp_servers.shell_mcp.server import mcp as shell_mcp
from app.mcp.mcp_servers.tavily_mcp.server import mcp as tavily_mcp
from app.mcp.mcp_servers.time_mcp.server import mcp as time_mcp
from app.mcp.mcp_servers.weather_mcp.server import mcp as weather_mcp


class MCPRegistry:
    """Hold static server registrations."""

    def __init__(self) -> None:
        self._servers: dict[str, Any] = {
            "time-mcp": time_mcp,
            "context7-mcp": settings.mcp.context7_mcp.model_dump(mode="json"),
            "weather-mcp": weather_mcp,
            "tavily-mcp": tavily_mcp,
            "code-exec-mcp": code_exec_mcp,
            "file-mcp": file_mcp,
            "shell-mcp": shell_mcp,
        }

    def get_servers(self) -> dict[str, Any]:
        return dict(self._servers)
