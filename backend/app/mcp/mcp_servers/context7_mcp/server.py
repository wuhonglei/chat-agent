"""
Context7 MCP Server（代理模式）
通过 create_proxy 代理远程 https://mcp.context7.com/mcp，并支持 ResponseCachingMiddleware 缓存。
"""

from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy

from app.mcp.cache import add_response_caching_if_enabled
from app.utils.mcp import create_mcp_http_client_with_ssl_config

from .config import config

httpx_client_factory = create_mcp_http_client_with_ssl_config(False)
http_transport = StreamableHttpTransport(
    url=config.url,
    headers=config.headers,
    httpx_client_factory=httpx_client_factory,
)
mcp = create_proxy(http_transport, name="Context7 MCP")
add_response_caching_if_enabled(mcp, config.cache_config)
