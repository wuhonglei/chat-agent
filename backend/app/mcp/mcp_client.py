"""
统一的 MCP Client 管理器
用于连接和管理多个 MCP Server，提供统一的工具调用接口
"""

import asyncio
from loguru import logger
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport, StreamableHttpTransport
from fastmcp import FastMCP

# 导入 MCP servers
from app.mcp.mcp_servers.weather_mcp.server import mcp as weather_mcp
from app.mcp.mcp_servers.tavily_mcp.server import mcp as tavily_mcp


mcp_config = {
    "mcpServers": {
        "context7": {
            "url": "https://mcp.context7.com/mcp",
            "headers": {
                "CONTEXT7_API_KEY": "ctx7sk-23e02d48-44b5-47c5-a705-09cdf771a69b"
            }
        },
        "weather-mcp": weather_mcp,
        "tavily-mcp": tavily_mcp,
    }
}


class MCPClientManager:
    """
    MCP Client 管理器
    负责管理多个 MCP Server 的连接和工具调用
    """

    def __init__(self):
        """初始化 MCP Client 管理器"""
        self.servers: Dict[str, Any] = {}  # MCP server 实例
        self.clients: Dict[str, Client] = {}  # Client 实例
        self.tools_map: Dict[str, str] = {}  # 工具名 -> server 名映射
        self._initialized = False

    async def initialize(self) -> None:
        """初始化所有 MCP Server 连接"""
        if self._initialized:
            logger.warning("MCPClientManager 已经初始化")
            return

        logger.info("开始初始化 MCP Client Manager...")

        # 注册所有 MCP servers
        self.servers = mcp_config["mcpServers"]

        # 为每个 server 创建 client
        for server_name, server_instance in self.servers.items():
            try:
                # 根据服务器类型选择不同的传输方式
                if isinstance(server_instance, FastMCP):
                    # 本地 FastMCP 服务器
                    transport = FastMCPTransport(server_instance)
                    logger.info(f"使用 FastMCPTransport 连接本地服务器: {server_name}")
                elif isinstance(server_instance, dict) and "url" in server_instance:
                    # 远程 HTTP 服务器
                    transport = StreamableHttpTransport(
                        url=server_instance["url"],
                        headers=server_instance.get("headers", {})
                    )
                    logger.info(
                        f"使用 StreamableHttpTransport 连接远程服务器: {server_name}")
                else:
                    # 其他类型的服务器实例
                    transport = server_instance
                    logger.info(f"使用自定义传输方式连接服务器: {server_name}")

                client = Client(transport=transport)
                self.clients[server_name] = client

                logger.info(f"✓ 已注册 MCP Server: {server_name}")
            except Exception as e:
                logger.error(f"✗ 注册 {server_name} 失败: {e}")
                raise

        # 建立连接并构建工具映射
        for server_name, client in self.clients.items():
            try:
                await client.__aenter__()

                # 获取该 server 的所有工具
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = tool.name
                    if tool_name in self.tools_map:
                        logger.warning(
                            f"工具名冲突: {tool_name} 同时存在于 "
                            f"{self.tools_map[tool_name]} 和 {server_name}"
                        )
                    self.tools_map[tool_name] = server_name

                logger.info(f"✓ 已连接 {server_name}，注册了 {len(tools)} 个工具")

            except Exception as e:
                logger.error(f"✗ 连接 {server_name} 失败: {e}")
                # 清理已创建的连接
                await self.cleanup()
                raise

        self._initialized = True
        logger.info(
            f"✓ MCP Client Manager 初始化完成，共注册 {len(self.tools_map)} 个工具")

    async def cleanup(self) -> None:
        """清理所有连接"""
        logger.info("开始清理 MCP Client Manager...")

        for server_name, client in self.clients.items():
            try:
                await client.__aexit__(None, None, None)
                logger.info(f"✓ 已断开 {server_name}")
            except Exception as e:
                logger.error(f"✗ 断开 {server_name} 时出错: {e}")

        self.clients.clear()
        self.tools_map.clear()
        self._initialized = False
        logger.info("✓ MCP Client Manager 清理完成")

    async def list_all_tools(self) -> Dict[str, List[Any]]:
        """
        列出所有可用的工具

        Returns:
            Dict[str, List]: server_name -> tools 的映射
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        all_tools = {}
        for server_name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                all_tools[server_name] = tools
            except Exception as e:
                logger.error(f"获取 {server_name} 的工具列表失败: {e}")
                all_tools[server_name] = []

        return all_tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        调用指定的工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果

        Raises:
            ValueError: 工具不存在
            RuntimeError: Manager 未初始化
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        # 查找工具所属的 server
        if tool_name not in self.tools_map:
            available_tools = ", ".join(self.tools_map.keys())
            raise ValueError(
                f"工具 '{tool_name}' 不存在。"
                f"可用工具: {available_tools}"
            )

        server_name = self.tools_map[tool_name]
        client = self.clients[server_name]

        try:
            logger.info(f"调用工具: {tool_name} (来自 {server_name})")
            result = await client.call_tool(tool_name, arguments or {})
            logger.info(f"✓ 工具 {tool_name} 执行成功")
            return result
        except Exception as e:
            logger.error(f"✗ 工具 {tool_name} 执行失败: {e}")
            raise

    async def get_tool_info(self, tool_name: str) -> Optional[Any]:
        """
        获取工具的详细信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息对象，如果工具不存在则返回 None
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        if tool_name not in self.tools_map:
            return None

        server_name = self.tools_map[tool_name]
        client = self.clients[server_name]

        tools = await client.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool

        return None

    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """
        获取工具所属的 server 名称

        Args:
            tool_name: 工具名称

        Returns:
            server 名称，如果工具不存在则返回 None
        """
        return self.tools_map.get(tool_name)

    @asynccontextmanager
    async def managed_session(self):
        """
        上下文管理器，自动处理初始化和清理

        Usage:
            async with manager.managed_session():
                result = await manager.call_tool("search_city", {"location": "北京"})
        """
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()

    async def health_check(self) -> Dict[str, bool]:
        """
        检查所有 server 的健康状态

        Returns:
            Dict[str, bool]: server_name -> 是否健康
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        health_status = {}
        for server_name, client in self.clients.items():
            try:
                # 尝试列出工具来检查连接是否正常
                await client.list_tools()
                health_status[server_name] = True
                logger.info(f"✓ {server_name} 健康检查通过")
            except Exception as e:
                health_status[server_name] = False
                logger.error(f"✗ {server_name} 健康检查失败: {e}")

        return health_status

    async def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        获取格式化后的工具列表，用于 LLM function calling

        Returns:
            List[Dict]: 格式化的工具列表
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        all_tools = await self.list_all_tools()
        formatted_tools = []

        for server_name, tools in all_tools.items():
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                })

        return formatted_tools


# 创建全局单例
mcp_client_manager = MCPClientManager()


async def get_mcp_manager() -> MCPClientManager:
    """
    获取 MCP Client Manager 实例（用于依赖注入）

    Returns:
        MCPClientManager 实例
    """
    if not mcp_client_manager._initialized:
        await mcp_client_manager.initialize()
    return mcp_client_manager
