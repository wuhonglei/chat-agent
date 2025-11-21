from typing import Any
import httpx
from mcp.shared._httpx_utils import McpHttpClientFactory


def create_mcp_http_client_with_ssl_config(
    verify_ssl: bool = True
) -> McpHttpClientFactory:
    """创建支持 SSL 验证配置的 MCP HTTP 客户端工厂"""
    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        # 使用 MCP 默认配置，但添加 SSL 验证控制
        kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "verify": verify_ssl,  # 控制 SSL 证书验证
        }

        # Handle timeout
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0)
        else:
            kwargs["timeout"] = timeout

        # Handle headers
        if headers is not None:
            kwargs["headers"] = headers

        # Handle authentication
        if auth is not None:
            kwargs["auth"] = auth

        return httpx.AsyncClient(**kwargs)

    return factory
