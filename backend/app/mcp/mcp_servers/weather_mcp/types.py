"""和风天气 MCP 类型定义"""

from typing import Protocol

from app.schemas.config import MCPCacheConfig


class WeatherConfigProtocol(Protocol):
    """天气 MCP 配置协议：主应用 WeatherMCPConfig 与独立运行 Settings 均兼容"""

    QWEATHER_API_KEY: str
    QWEATHER_BASE_URL: str
    QWEATHER_TIMEOUT: int
    cache_config: MCPCacheConfig
