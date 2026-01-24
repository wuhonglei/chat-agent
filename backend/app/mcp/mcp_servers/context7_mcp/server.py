"""
Context7 MCP Server（代理模式）
通过 FastMCP.as_proxy 代理远程 https://mcp.context7.com/mcp，并支持 ResponseCachingMiddleware 缓存。
"""

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.proxy import ProxyClient

from app.mcp.cache import add_response_caching_if_enabled

from .config import config

http_transport = StreamableHttpTransport(
    url=config.url,
    headers=config.headers,
)
mcp = FastMCP.as_proxy(ProxyClient(http_transport), name="Context7 MCP")
add_response_caching_if_enabled(mcp, config.cache_config)
