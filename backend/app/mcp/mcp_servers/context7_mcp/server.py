"""
Context7 MCP Server（代理模式）
通过 create_proxy 代理远程 https://mcp.context7.com/mcp。
"""

from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy

from .config import config

http_transport = StreamableHttpTransport(
    url=config.url,
    headers=config.headers,
)
mcp = create_proxy(http_transport, name="Context7 MCP")
