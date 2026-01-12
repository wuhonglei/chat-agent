"""Chat service for RAG-based Q&A"""
from collections.abc import AsyncGenerator

from app.core.config import settings
from app.schemas.chat import ChatMessageItemReq, ChatRequest, CollectedResponse
from app.schemas.token_stats import TotalTokenStats
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.mcp.mcp_client import MCPClientManager
from app.services.component_schema_service import ComponentSchemaService
from app.services.context_compression_service import ContextCompressionService
from app.agents import (
    MCPToolsAgent,
    ComponentToolsAgent,
    ResponseGenerationAgent,
    TitleGenerationAgent,
    ContextCompressionAgent,
)
from app.utils.model import format_sse_message


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, think_mode: bool, mcp_manager: MCPClientManager):
        self.debug = settings.app.debug
        self.schema_service = ComponentSchemaService(
            debug=self.debug)  # 复用 ComponentSchemaService 实例

        # 初始化各个Agent
        self.title_generation_agent = TitleGenerationAgent(
            think_mode=False, llm_config=settings.tool_call_model)
        # MCP工具和组件工具使用tool配置
        self.mcp_tools_agent = MCPToolsAgent(
            think_mode=think_mode, llm_config=settings.tool_call_model, mcp_manager=mcp_manager)
        self.component_tools_agent = ComponentToolsAgent(
            think_mode=think_mode, llm_config=settings.tool_call_model, schema_service=self.schema_service)
        # 响应生成和标题生成使用llm配置
        self.response_generation_agent = ResponseGenerationAgent(
            think_mode=think_mode, llm_config=settings.response_model, schema_service=self.schema_service)
        # 上下文压缩Agent
        self.context_compression_agent = ContextCompressionAgent(
            think_mode=False, llm_config=settings.tool_call_model)
        # 上下文压缩服务
        self.context_compression_service = ContextCompressionService(
            model_name=settings.tool_call_model.model_name,
            token_calculator=self.response_generation_agent.token_calculator,
            compression_threshold=settings.compression.iteration_compression.compression_trigger_threshold
        )

    async def stream_message(
        self,
        chat_request: ChatRequest,
        history: list[ChatMessageItemReq],
        client_ip: str | None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response using agent architecture"""
        start_time = get_current_time()
        try:
            user_message = chat_request.content
            logger.info(
                "Starting chat message stream",
                user_message_length=len(user_message),
                history_length=len(history),
                client_ip=client_ip,
                has_component_tools=bool(
                    chat_request.component_tools_for_backend),
            )

            # 阶段1: MCP工具调用
            logger.debug("Starting MCP tools agent execution")
            mcp_start_time = get_current_time()
            async for message in self.mcp_tools_agent.stream_execute(
                chat_request,
                history,
                client_ip,
            ):
                yield message
            mcp_duration = get_time_duration(mcp_start_time)
            logger.debug(
                "MCP tools agent execution completed",
                duration=mcp_duration,
                tool_calls_count=len(self.mcp_tools_agent.output_messages),
            )

            # 阶段2: 组件工具调用
            component_tools_for_backend = chat_request.component_tools_for_backend
            if component_tools_for_backend:
                logger.debug(
                    "Starting component tools agent execution",
                    component_tools_count=len(component_tools_for_backend),
                )
                component_start_time = get_current_time()
                async for message in self.component_tools_agent.stream_execute(
                    user_message,
                    self.mcp_tools_agent.output_messages,
                    component_tools_for_backend,
                ):
                    yield message
                component_duration = get_time_duration(component_start_time)
                logger.debug(
                    "Component tools agent execution completed",
                    duration=component_duration,
                    tool_calls_count=len(
                        self.component_tools_agent.output_messages),
                )
            else:
                logger.debug(
                    "Skipping component tools agent (no component tools)")

            # 阶段2.5: 上下文压缩（可选，在MCP工具和响应生成之间）
            compression_result = await self.context_compression_service.compress_tool_messages(
                self.mcp_tools_agent.output_messages
            )
            compressed_mcp_messages = compression_result.compressed_messages

            # Log compression statistics
            if compression_result.was_compressed:
                logger.debug(
                    "Context compression applied",
                    duration=compression_result.duration,
                    original_length=compression_result.original_length,
                    compressed_length=compression_result.compressed_length,
                    compression_ratio=compression_result.compression_ratio,
                )
            else:
                logger.debug(
                    "Context compression skipped - below threshold",
                    original_length=compression_result.original_length,
                    threshold=self.context_compression_service.context_monitor.compression_threshold
                )

            # 阶段3: 最终响应生成
            logger.debug("Starting response generation agent execution")
            response_start_time = get_current_time()
            async for chunk in self.response_generation_agent.stream_execute(
                history,
                user_message,
                compressed_mcp_messages,
                self.component_tools_agent.output_messages,
            ):
                yield chunk
            response_duration = get_time_duration(response_start_time)
            logger.debug(
                "Response generation agent execution completed",
                duration=response_duration,
            )

            total_duration = get_time_duration(start_time)
            logger.info(
                "Chat message stream completed",
                total_duration=total_duration,
                mcp_tool_calls_count=len(self.mcp_tools_agent.output_messages),
                component_tool_calls_count=len(
                    self.component_tools_agent.output_messages),
            )
            return

        except Exception as e:
            total_duration = get_time_duration(start_time)
            logger.error(
                "Failed to stream message",
                error=e,
                duration=total_duration,
            )
            yield format_sse_message('error', {
                'content': str(e),
            })
            return

    async def generate_title(self, user_message: str) -> str:
        """Generate title for the chat"""
        return await self.title_generation_agent.execute(user_message)

    def get_collected_response(self) -> CollectedResponse:
        """获取已收集的助手消息内容"""
        # 收集所有 token 统计信息
        total_token_stats = TotalTokenStats(
            mcp_tools=self.mcp_tools_agent.token_stats,
            component_tools=self.component_tools_agent.token_stats,
            response_generation=self.response_generation_agent.token_stats,
            title_generation=self.title_generation_agent.token_stats,
        )

        return CollectedResponse(
            content=self.response_generation_agent.content,
            reasoning=self.response_generation_agent.reasoning,
            tool_calls=[tool_call.model_dump(mode="json")
                        for tool_call in self.mcp_tools_agent.output_messages],
            component_tool_calls=[tool_call.model_dump(mode="json")
                                  for tool_call in self.component_tools_agent.output_messages],
            tool_calls_duration=self.mcp_tools_agent.duration,
            component_tool_calls_duration=self.component_tools_agent.duration,
            reasoning_duration=self.response_generation_agent.reasoning_duration,
            content_duration=self.response_generation_agent.content_duration,
            total_duration=self.response_generation_agent.total_duration,
            token_stats=total_token_stats.model_dump(mode="json") if any([
                self.mcp_tools_agent.token_stats,
                self.component_tools_agent.token_stats,
                self.response_generation_agent.token_stats,
                self.title_generation_agent.token_stats,
            ]) else None,
        )
