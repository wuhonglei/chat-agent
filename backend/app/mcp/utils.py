"""
MCP 通用工具。

inject_mcp_env_vars 已移除：主应用内 tavily/confluence/weather 直接使用
settings.mcp.xxx_mcp（含 Nacos 下发的 cache_config）；独立运行仍使用各 MCP 的 .config + .env。
"""
