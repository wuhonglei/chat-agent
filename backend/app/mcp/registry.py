"""Configuration-driven MCP registry.

Reads ``settings.mcp.servers`` to decide which MCP servers to load and how
to connect to them.  Three transport types are supported:

* **fastmcp** – in-process ``FastMCP`` instance, loaded via ``importlib``.
* **http**    – remote Streamable HTTP server (``url`` + ``headers``).
* **stdio**   – subprocess server (``command`` + ``args``).

Servers can be disabled at config level (``enabled: false``) without code
changes.
"""

from __future__ import annotations

import importlib
from typing import Any, assert_never

from app.core.config import settings
from app.schemas.config import MCPServerEntry
from app.utils.logger import logger


class MCPRegistry:
    """Hold server registrations, driven by configuration."""

    def __init__(self) -> None:
        self._servers: dict[str, Any] = {}
        self._load_from_config()

    def get_servers(self) -> dict[str, Any]:
        return dict(self._servers)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_from_config(self) -> None:
        """Build the server map from ``settings.mcp.servers``."""
        server_configs: dict[str, MCPServerEntry] = settings.mcp.servers
        for name, entry in server_configs.items():
            if not entry.enabled:
                logger.info("MCP Server disabled by config", server_name=name)
                continue
            try:
                self._register(name, entry)
            except Exception as exc:
                logger.error(
                    "Failed to register MCP Server",
                    server_name=name,
                    transport=entry.transport,
                    error=exc,
                )

    def _register(self, name: str, entry: MCPServerEntry) -> None:
        """Resolve *entry* into a server object and store it."""
        transport = entry.transport

        if transport == "fastmcp":
            self._register_fastmcp(name, entry)
        elif transport == "http":
            self._register_http(name, entry)
        elif transport == "stdio":
            self._register_stdio(name, entry)
        else:
            assert_never(transport)

    # ------------------------------------------------------------------
    # Transport-specific registration
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_server_config(entry: MCPServerEntry) -> None:
        """Call ``configure(entry)`` on the sibling ``config`` module if present."""
        if not entry.module:
            return
        config_module_name = f"{entry.module.rsplit('.', 1)[0]}.config"
        try:
            config_mod = importlib.import_module(config_module_name)
        except ModuleNotFoundError:
            return
        configure = getattr(config_mod, "configure", None)
        if callable(configure):
            configure(entry)

    def _register_fastmcp(self, name: str, entry: MCPServerEntry) -> None:
        """Dynamically import a FastMCP instance from the given module."""
        # Lazy import to avoid circular dependency at module level
        from fastmcp import FastMCP

        if not entry.module:
            raise ValueError(
                f"MCP Server '{name}' uses fastmcp transport but 'module' is not set"
            )
        self._inject_server_config(entry)
        module = importlib.import_module(entry.module)
        instance = getattr(module, entry.instance)
        if not isinstance(instance, FastMCP):
            raise TypeError(
                f"Attribute '{entry.instance}' in module '{entry.module}' "
                f"is {type(instance).__name__}, expected FastMCP"
            )
        self._servers[name] = instance
        logger.info(
            "MCP Server registered (fastmcp / in-process)",
            server_name=name,
            module=entry.module,
            instance=entry.instance,
        )

    def _register_http(self, name: str, entry: MCPServerEntry) -> None:
        """Register a remote HTTP/StreamableHTTP server."""
        url = entry.url
        headers = dict(entry.headers)

        if not url:
            raise ValueError(
                f"MCP Server '{name}' uses http transport but 'url' is not set"
            )

        self._servers[name] = {"url": url, "headers": headers}
        logger.info(
            "MCP Server registered (http / remote)",
            server_name=name,
            url=url,
        )

    def _register_stdio(self, name: str, entry: MCPServerEntry) -> None:
        """Register a stdio subprocess server."""
        if not entry.command:
            raise ValueError(
                f"MCP Server '{name}' uses stdio transport but 'command' is not set"
            )
        server_dict: dict[str, Any] = {"command": entry.command}
        if entry.args:
            server_dict["args"] = list(entry.args)
        if entry.env:
            server_dict["env"] = dict(entry.env)
        self._servers[name] = server_dict
        logger.info(
            "MCP Server registered (stdio / subprocess)",
            server_name=name,
            command=entry.command,
        )
