"""Chat service for RAG-based Q&A"""
from collections.abc import AsyncGenerator

from app.core.config import settings
from app.schemas.chat import ChatMessageItemReq, ChatRequest, CollectedResponse
from app.utils.logger import logger
from app.mcp.mcp_client import MCPClientManager
from app.services.component_schema_service import ComponentSchemaService
from app.prompts.prompt_utils import get_user_message_with_component_data
from app.agents import (
    MCPToolsAgent,
    ComponentToolsAgent,
    ResponseGenerationAgent,
    TitleGenerationAgent,
)


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.debug = settings.app.debug
        self.schema_service = ComponentSchemaService(
            debug=self.debug)  # 复用 ComponentSchemaService 实例

        # 初始化各个Agent
        # MCP工具和组件工具使用tool配置
        self.mcp_tools_agent = MCPToolsAgent(
            settings.tool, mcp_manager)
        self.component_tools_agent = ComponentToolsAgent(
            settings.tool, self.schema_service)
        # 响应生成和标题生成使用llm配置
        self.response_generation_agent = ResponseGenerationAgent(
            settings.llm)
        self.title_generation_agent = TitleGenerationAgent(
            settings.llm)

    async def stream_message(
        self,
        chat_request: ChatRequest,
        history: list[ChatMessageItemReq],
        client_ip: str | None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response using agent architecture"""
        try:
            think_mode = chat_request.think_mode
            user_message = chat_request.content

            # 阶段1: MCP工具调用
            async for message in self.mcp_tools_agent.stream_execute(
                chat_request,
                history,
                client_ip,
            ):
                yield message

            # 阶段2: 组件工具调用
            component_tools_for_backend = chat_request.component_tools_for_backend
            if component_tools_for_backend:
                async for message in self.component_tools_agent.stream_execute(
                    user_message,
                    self.mcp_tools_agent.collected_messages,
                    component_tools_for_backend,
                    think_mode,
                ):
                    yield message

            # 将组件数据拼接到 user_message
            final_user_message = get_user_message_with_component_data(
                user_message,
                self.component_tools_agent.collected_messages,
                self.schema_service.get_schema_cache()
            )

            # 阶段3: 最终响应生成
            async for chunk in self.response_generation_agent.stream_execute(
                history,
                final_user_message,
                self.mcp_tools_agent.collected_messages,
                self.component_tools_agent.collected_messages,
                think_mode,
            ):
                yield chunk
            return

        except Exception as e:
            logger.error("Failed to stream message", error=e)
            raise

    async def generate_title(self, user_message: str) -> str:
        """Generate title for the chat"""
        return await self.title_generation_agent.execute(user_message)

    def get_collected_response(self) -> CollectedResponse:
        """获取已收集的助手消息内容"""
        return CollectedResponse(
            content=self.response_generation_agent.content,
            reasoning=self.response_generation_agent.reasoning,
            tool_calls=[tool_call.model_dump(
            ) for tool_call in self.mcp_tools_agent.collected_messages],
            component_tool_calls=[tool_call.model_dump(
            ) for tool_call in self.component_tools_agent.collected_messages],
            tool_calls_duration=self.mcp_tools_agent.duration,
            component_tool_calls_duration=self.component_tools_agent.duration,
            reasoning_duration=self.response_generation_agent.reasoning_duration,
            content_duration=self.response_generation_agent.content_duration,
            total_duration=self.response_generation_agent.total_duration,
        )
