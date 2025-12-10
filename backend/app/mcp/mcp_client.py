"""
统一的 MCP Client 管理器
用于连接和管理多个 MCP Server，提供统一的工具调用接口
"""

import asyncio
import copy
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastmcp import Client, FastMCP
from fastmcp.client.transports import (
    FastMCPTransport,
    StdioTransport,
    StreamableHttpTransport,
)

from app.core.config import settings
from app.models.mcp import MCPConfigForFeDict
from app.mcp.utils import inject_mcp_env_vars
from app.utils.logger import logger
from app.utils.mcp import create_mcp_http_client_with_ssl_config

VERIFY_SSL = not settings.app.debug

# 在导入 MCP servers 之前注入 MCP 环境变量
# 这必须在导入 MCP servers 之前执行，因为它们的 config.py 需要这些环境变量
inject_mcp_env_vars(settings.mcp)

# 导入 MCP servers（必须在注入环境变量之后）
# 注意：这些导入的顺序很重要，不要使用自动格式化工具调整顺序
# fmt: off
from app.mcp.mcp_servers.time_mcp.server import mcp as time_mcp
from app.mcp.mcp_servers.weather_mcp.server import mcp as weather_mcp
from app.mcp.mcp_servers.tavily_mcp.server import mcp as tavily_mcp
from app.mcp.mcp_servers.confluence_mcp.server import mcp as mcp_confluence
from app.mcp.mcp_servers.confluence_mcp.server import check_availability as confluence_check_availability
from app.mcp.mcp_servers.code_exec_mcp.server import mcp as code_exec_mcp
from app.mcp.mcp_servers.ip_locator_mcp.server import mcp as ip_locator_mcp
# fmt: on

# 导入 MCP servers
# 对于需要可用性检测的服务器，可以配置 availability_checker 函数
# 格式: {"server": server_instance, "availability_checker": check_function}
# 或者直接使用 server_instance（不需要检测的服务器）
mcp_config = {
    "mcpServers": {
        "ip-locator-mcp": ip_locator_mcp,
        "time-mcp": time_mcp,
        "context7": {
            "url": "https://mcp.context7.com/mcp",
            "headers": {
                "CONTEXT7_API_KEY": settings.mcp.context7.api_key
            },
            "verify_ssl": VERIFY_SSL
        },
        "confluence-mcp": {
            "server": mcp_confluence,
            "availability_checker": confluence_check_availability,
        },
        "weather-mcp": weather_mcp,
        "tavily-mcp": tavily_mcp,
        "code-exec-mcp": code_exec_mcp,
    }
}

mcp_config_for_fe: List[MCPConfigForFeDict] = [{
    'id': 'context7',
    'name': 'Context7',
    'icon': 'https://context7.com/favicon.ico',
    'description': '为 LLM 和 AI 代码编辑器提供最新文档',
}, {
    'id': 'confluence-mcp',
    'name': 'Confluence',
    'icon': 'https://www.atlassian.com/favicon.ico',
    'description': 'Shopee 内部公司知识库查询',
}, {
    'id': 'weather-mcp',
    'name': '天气查询',
    'icon': 'https://www.qweather.com/favicon.ico',
    'description': '天气信息查询',
}, {
    'id': 'tavily-mcp',
    'name': '联网搜索',
    'icon': 'https://www.tavily.com/favicon.ico',
    'description': '联网搜索和内容提取',
}, {
    'id': 'code-exec-mcp',
    'name': '代码执行',
    'icon': 'https://www.python.org/static/favicon.ico',
    'description': '安全的 Python 代码执行服务，使用沙箱隔离确保安全性',
}]


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
        self.tools_by_server: Dict[str, List[Any]] = {}  # server 名 -> 工具列表映射
        self._initialized = False

    async def initialize(self) -> None:
        """初始化所有 MCP Server 连接"""
        if self._initialized:
            logger.warning("MCPClientManager already initialized")
            return

        logger.info("Initializing MCP Client Manager")

        # 注册所有 MCP servers
        self.servers = copy.deepcopy(mcp_config["mcpServers"])

        # 为每个 server 创建 client
        # 使用 list() 创建副本，以便在迭代时安全地修改字典
        for server_name, server_config in list(self.servers.items()):
            # 检查是否需要可用性检测
            # 如果配置是字典且包含 availability_checker，则进行检测
            availability_checker = None
            server_instance = server_config

            if isinstance(server_config, dict) and "availability_checker" in server_config:
                availability_checker = server_config.get(
                    "availability_checker")
                server_instance = server_config.get("server", server_config)
                # 更新 self.servers 中的值，使用实际的 server 实例
                self.servers[server_name] = server_instance

            # 如果有可用性检测函数，先进行检测
            if availability_checker and callable(availability_checker):
                logger.info("Checking server availability",
                            server_name=server_name)
                try:
                    is_available = await availability_checker()
                    if not is_available:
                        logger.warning(
                            "Server unavailable, skipping",
                            server_name=server_name,
                        )
                        # 从 servers 中移除，避免后续处理
                        del self.servers[server_name]
                        continue
                    logger.info("Server availability check passed",
                                server_name=server_name)
                except Exception as e:
                    logger.warning(
                        "Server availability check failed",
                        server_name=server_name,
                        error=str(e),
                    )
                    del self.servers[server_name]
                    continue

            try:
                # 根据服务器类型选择不同的传输方式
                if isinstance(server_instance, FastMCP):
                    # 本地 FastMCP 服务器
                    transport = FastMCPTransport(server_instance)
                    logger.info(
                        "Using FastMCPTransport for local server",
                        server_name=server_name,
                        transport_type="FastMCPTransport",
                    )
                elif isinstance(server_instance, dict) and "url" in server_instance:
                    # 远程 HTTP 服务器
                    verify_ssl = server_instance.get(
                        "verify_ssl", True)  # 默认启用 SSL 验证
                    httpx_client_factory = create_mcp_http_client_with_ssl_config(
                        verify_ssl)

                    transport = StreamableHttpTransport(
                        url=server_instance["url"],
                        headers=server_instance.get("headers", {}),
                        httpx_client_factory=httpx_client_factory
                    )
                    logger.info(
                        "Using StreamableHttpTransport for remote server",
                        server_name=server_name,
                        transport_type="StreamableHttpTransport",
                        verify_ssl=verify_ssl,
                    )
                elif isinstance(server_instance, dict) and "command" in server_instance:
                    transport = StdioTransport(**server_instance)
                    logger.info(
                        "Using StdioTransport for local server",
                        server_name=server_name,
                        transport_type="StdioTransport",
                    )
                else:
                    # 其他类型的服务器实例
                    transport = server_instance
                    logger.info(
                        "Using custom transport for server",
                        server_name=server_name,
                        transport_type="custom",
                    )

                client = Client(transport=transport)
                self.clients[server_name] = client

                logger.info("MCP Server registered", server_name=server_name)
            except Exception as e:
                logger.error(
                    "Failed to register MCP Server",
                    error=e,
                    server_name=server_name,
                )

        # 建立连接并构建工具映射
        for server_name, client in self.clients.items():
            try:
                # 获取该 server 的所有工具
                async with client:
                    tools = await client.list_tools()
                    self.tools_by_server[server_name] = tools
                for tool in tools:
                    tool_name = tool.name
                    if tool_name in self.tools_map:
                        logger.warning(
                            "Tool name conflict",
                            tool_name=tool_name,
                            existing_server=self.tools_map[tool_name],
                            new_server=server_name,
                        )
                    self.tools_map[tool_name] = server_name

                logger.info(
                    "MCP Server connected",
                    server_name=server_name,
                    tool_count=len(tools),
                )

            except Exception as e:
                logger.error(
                    "Failed to connect MCP Server",
                    error=e,
                    server_name=server_name,
                )

        self._initialized = True
        logger.info(
            "MCP Client Manager initialized",
            total_tools=len(self.tools_map),
        )

    def cleanup(self) -> None:
        """清理所有连接"""
        logger.info("Cleaning up MCP Client Manager")
        self.clients.clear()
        self.tools_map.clear()
        self._initialized = False
        logger.info("MCP Client Manager cleanup completed")

    async def list_tools(self, server_names: Optional[list[str]] = None) -> Dict[str, List[Any]]:
        """
        列出所有可用的工具

        Returns:
            Dict[str, List]: server_name -> tools 的映射
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        all_tools = {}
        server_names = self.clients.keys() if server_names is None else server_names
        if not server_names:
            return {}

        async def list_tools_for_server(server_name: str) -> List[Any]:
            if server_name not in self.clients:
                return []

            client = self.clients[server_name]
            async with client:
                tools = await client.list_tools()
            return tools

        tasks = [list_tools_for_server(server_name)
                 for server_name in server_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for server_name, tools in zip(server_names, results):
            if isinstance(tools, Exception):
                logger.error(
                    "Failed to get tools list",
                    error=tools,
                    server_name=server_name,
                )
            else:
                all_tools[server_name] = tools

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
            logger.info(
                "Calling tool",
                tool_name=tool_name,
                server_name=server_name,
            )
            async with client:
                result = await client.call_tool(tool_name, arguments or {}, timeout=30)
            logger.info(
                "Tool executed successfully",
                tool_name=tool_name,
                server_name=server_name,
            )
            return result
        except Exception as e:
            logger.error(
                "Tool execution failed",
                error=e,
                tool_name=tool_name,
                server_name=server_name,
            )
            raise

    @staticmethod
    def format_mcp_result(result: Any) -> str:
        """
        格式化 MCP 结果
        """
        # 处理结果
        if hasattr(result, 'content'):
            # 如果结果有 content 属性
            if isinstance(result.content, list):
                # 如果是列表，提取所有文本内容
                text_parts = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                return "\n".join(text_parts)
            elif hasattr(result.content, 'text'):
                return result.content.text
            else:
                return str(result.content)
        else:
            return str(result)

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

        async with client:
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
            self.cleanup()

    async def health_check(self) -> Dict[str, bool]:
        """
        检查所有 server 的健康状态

        Returns:
            Dict[str, bool]: server_name -> 是否健康
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        async def check_single_server(server_name: str, client) -> tuple[str, bool]:
            """检查单个服务器的健康状态"""
            try:
                # # 尝试列出工具来检查连接是否正常(为了避免该请求比较耗时，因此临时注释)
                # async with client:
                #     await client.list_tools()
                logger.info("Health check passed", server_name=server_name)
                if server_name in self.tools_by_server:
                    return server_name, True
                else:
                    return server_name, False
            except Exception as e:
                logger.error(
                    "Health check failed",
                    error=e,
                    server_name=server_name,
                )
                return server_name, False

        # 并发执行所有服务器的健康检查
        tasks = [
            check_single_server(server_name, client)
            for server_name, client in self.clients.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        health_status = {}
        for result in results:
            if isinstance(result, Exception):
                # 如果任务本身出现异常，记录错误
                logger.error("Health check task exception", error=result)
            else:
                server_name, is_healthy = result
                health_status[server_name] = is_healthy

        return health_status

    async def get_mcp_config_for_fe(self) -> List[MCPConfigForFeDict]:
        """
        获取用于前端展示的 MCP 配置

        Returns:
            List[Dict[str, Any]]: MCP 配置列表
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        health_status = await self.health_check()
        mcp_config_for_fe_copy = copy.deepcopy(mcp_config_for_fe)
        for server in mcp_config_for_fe_copy:
            server['online'] = health_status.get(server['id'], False)
        return mcp_config_for_fe_copy

    async def get_tools_for_llm(self, server_names: Optional[list[str]], client_ip: str | None = None) -> List[Dict[str, Any]]:
        """
        获取格式化后的工具列表，用于 LLM function calling

        Returns:
            List[Dict]: 格式化的工具列表
        """
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

        formatted_tools = []
        final_server_names = set(self.tools_by_server.keys(
        ))if server_names is None else set(server_names)
        if client_ip:
            final_server_names.add("ip-locator-mcp")
        else:
            final_server_names.discard("ip-locator-mcp")

        for server_name in final_server_names:
            if server_name not in self.tools_by_server:
                continue
            tools = self.tools_by_server[server_name]
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
