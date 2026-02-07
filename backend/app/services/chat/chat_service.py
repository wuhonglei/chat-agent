"""Chat service for RAG-based Q&A"""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

from app.agents import (
    ComponentToolsAgent,
    MCPToolsAgent,
    ResponseGenerationAgent,
    TitleGenerationAgent,
)
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageItemWithToolCalls,
    ChatRequest,
    CollectedResponse,
    MessageStatus,
)
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.schemas.token_stats import TotalTokenStats
from app.services.component import ComponentSchemaService
from app.services.conversation import (
    ContextSummaryService,
    ConversationContextDbService,
)
from app.services.message import MessageDbService
from app.services.user import (
    UserProfileExtractionService,
    UserProfileItemDbService,
)
from app.utils.common import pick_fields
from app.utils.history_truncate import truncate_history_by_rounds_and_tokens
from app.utils.logger import logger
from app.utils.message import filter_tool_call_messages
from app.utils.model import format_sse_message
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator


async def _run_window_out_summary_only(
    conversation_id: str,
    truncated_messages: list[ChatMessageItem],
    summary_max_tokens: int,
) -> None:
    """仅做窗口外摘要并写入 user_context.recent_summary，供本轮回复生成时注入 system prompt。在问答开始前 await 调用。"""
    logger.info(
        "Running window-out summary (before response)",
        conversation_id=conversation_id,
        truncated_messages_count=len(truncated_messages),
        summary_max_tokens=summary_max_tokens,
    )
    try:
        summary_svc = ContextSummaryService()
        summary = await summary_svc.summarize_truncated_messages(
            truncated_messages, max_tokens=summary_max_tokens
        )
        if summary:
            with ConversationContextDbService() as ctx_svc:
                ctx_svc.upsert_conversation_context(
                    conversation_id,
                    recent_summary=summary,
                )
    except Exception as e:
        logger.warning(
            "Window-out summary task failed",
            conversation_id=conversation_id,
            error=e,
        )


async def _run_profile_extraction_only(
    user_id: str,
    conversation_id: str,
    user_message_content: str,
    assistant_content: str,
) -> None:
    """仅做用户事实/偏好归纳并写入 user_profile_items。需助手回复内容，在问答结束后异步执行。"""
    logger.info(
        "Running user profile extraction (after response)",
        user_id=user_id,
        conversation_id=conversation_id,
        user_message_content_length=len(user_message_content),
        assistant_content_length=len(assistant_content),
    )
    try:
        summary: str | None = None
        with ConversationContextDbService() as ctx_svc:
            summary = ctx_svc.get_conversation_context_summary(conversation_id)
        extraction_svc = UserProfileExtractionService()
        with UserProfileItemDbService() as item_svc:
            existing_facts, existing_prefs = item_svc.get_existing_texts(user_id)
            facts, preferences = await extraction_svc.extract_user_facts_preferences(
                user_message_content=user_message_content,
                assistant_content=assistant_content,
                summary=summary,
                existing_facts=existing_facts,
                existing_preferences=existing_prefs,
            )
            await item_svc.batch_upsert_items(
                user_id, facts=facts, preferences=preferences
            )
    except Exception as e:
        logger.warning(
            "User profile extraction task failed",
            user_id=user_id,
            conversation_id=conversation_id,
            error=e,
        )


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, think_mode: bool, mcp_manager: MCPClientManager):
        self.debug = settings.app.debug
        self.compression = settings.compression
        self.schema_service = ComponentSchemaService(
            debug=self.debug
        )  # 复用 ComponentSchemaService 实例

        self.token_calculator = TokenCalculator(settings.response_model.model_name)

        # 初始化各个Agent
        self.title_generation_agent = TitleGenerationAgent(
            think_mode=False, llm_config=settings.tool_call_model
        )
        # MCP工具和组件工具使用tool配置
        self.mcp_tools_agent = MCPToolsAgent(
            think_mode=think_mode,
            llm_config=settings.tool_call_model,
            mcp_manager=mcp_manager,
        )
        self.component_tools_agent = ComponentToolsAgent(
            think_mode=think_mode,
            llm_config=settings.tool_call_model,
            schema_service=self.schema_service,
        )
        # 响应生成和标题生成使用llm配置
        self.response_generation_agent = ResponseGenerationAgent(
            think_mode=think_mode,
            llm_config=settings.response_model,
            schema_service=self.schema_service,
        )

    async def stream_message(
        self,
        chat_request: ChatRequest,
        history_messages: list[ChatMessageItemWithToolCalls],
        client_ip: str | None,
        user_id: str | None = None,
        user_message_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response using agent architecture. user_id 用于注入 user_profile/user_context；user_message_id 用于落库 query_embedding。"""
        start_time = get_current_time()
        try:
            user_message = chat_request.content
            logger.info(
                "Starting chat message stream",
                user_message_length=len(user_message),
                history_messages_count=len(history_messages),
                client_ip=client_ip,
                has_component_tools=bool(chat_request.component_tools_for_backend),
            )

            with MessageDbService() as message_service:
                query_embedding = await message_service.persist_user_message_embedding(
                    user_message, user_message_id
                )

            # 阶段1: MCP工具调用
            logger.debug("Starting MCP tools agent execution")
            mcp_start_time = get_current_time()
            async for message in self.mcp_tools_agent.stream_execute(
                chat_request,
                history_messages,
                client_ip,
            ):
                yield message
            mcp_duration = get_time_duration(mcp_start_time)
            logger.debug(
                "MCP tools agent execution completed",
                duration=mcp_duration,
                tool_calls_count=len(self.mcp_tools_agent.output_messages),
            )
            filtered_mcp_tool_call_messages = filter_tool_call_messages(
                self.mcp_tools_agent.output_messages
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
                    filtered_mcp_tool_call_messages,
                    component_tools_for_backend,
                ):
                    yield message
                component_duration = get_time_duration(component_start_time)
                logger.debug(
                    "Component tools agent execution completed",
                    duration=component_duration,
                    tool_calls_count=len(self.component_tools_agent.output_messages),
                )
            else:
                logger.debug("Skipping component tools agent (no component tools)")
            filtered_component_tool_call_messages = filter_tool_call_messages(
                self.component_tools_agent.output_messages
            )

            # 阶段3: 最终响应生成
            logger.debug("Starting response generation agent execution")
            response_start_time = get_current_time()
            async for chunk in self.response_generation_agent.stream_execute(
                history_messages=history_messages,
                user_message=user_message,
                mcp_tool_call_messages=filtered_mcp_tool_call_messages,
                component_tool_call_messages=filtered_component_tool_call_messages,
                user_id=user_id,
                conversation_id=chat_request.conversation_id,
                query_embedding=query_embedding,
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
                mcp_tool_calls_count=len(filtered_mcp_tool_call_messages),
                component_tool_calls_count=len(filtered_component_tool_call_messages),
            )
            return

        except Exception as e:
            total_duration = get_time_duration(start_time)
            logger.error(
                "Failed to stream message",
                error=e,
                duration=total_duration,
            )
            yield format_sse_message(
                "error",
                {
                    "content": str(e),
                },
            )
            return

    async def generate_title(
        self, user_message: str, conversation_id: str | None = None
    ) -> str:
        """生成对话标题，包含 token 统计"""
        logger.info(
            "Regenerating conversation title",
            conversation_id=conversation_id,
        )
        title = await self.title_generation_agent.execute(user_message)
        token_stats = (
            self.title_generation_agent.token_stats.model_dump(mode="json")
            if self.title_generation_agent.token_stats
            else None
        )
        logger.info(
            "Title generated",
            conversation_id=conversation_id,
            title=title,
            title_length=len(title) if title else 0,
        )

        return format_sse_message(
            "title",
            {
                "id": conversation_id,
                "title": title,
                "token_stats": token_stats,
            },
        )

    def process_history_messages(
        self, history_messages: list[ChatMessageItem]
    ) -> list[ChatMessageItemWithToolCalls]:
        """
        处理对话历史：最后 2 条视为最后一轮（完整 tool 消息），其他轮用 summary/content/截断参与组装。
        返回扁平列表，供 _compose_messages 按条 format_chat_message_for_llm。
        """
        if not history_messages:
            return []

        threshold_tokens = self.compression.tool_message_summary_threshold_tokens

        # 最后一轮简单视为 history_messages 的最后 2 条
        last_round_start = max(0, len(history_messages) - 2)

        flat: list[ChatMessageItemWithToolCalls] = []

        for idx, msg in enumerate(history_messages):
            if msg.role == "user":
                flat.append(msg)
                continue
            if msg.role != "assistant":
                flat.append(msg)
                continue
            if not msg.tool_calls:
                flat.append(msg)
                continue

            # 按 DB 顺序 [assistant1, tool1, assistant2, tool2, ...] 逐条处理，assistant 为多条
            tool_calls_list: list[ToolCallMessage] = filter_tool_call_messages(
                msg.tool_calls
            )
            if not tool_calls_list:
                flat.append(msg)
                continue

            is_latest_tool_round = idx >= last_round_start

            # 按原始顺序输出：assistant1, tool1, assistant2, tool2, ...
            for m in tool_calls_list:
                if getattr(m, "role", None) == "assistant":
                    flat.append(cast(AssistantToolCallMessage, m))
                elif getattr(m, "role", None) == "tool":
                    tr = cast(ToolCallResultMessage, m)
                    if is_latest_tool_round:
                        flat.append(tr)
                        continue

                    # 其他轮：用 summary，无则 content≤threshold 用 content，否则截断
                    effective_content: str
                    if tr.summary and tr.summary.strip():
                        effective_content = tr.summary
                    else:
                        content_tokens = self.token_calculator.count_tokens(
                            tr.content or ""
                        )
                        if content_tokens <= threshold_tokens:
                            effective_content = tr.content or ""
                        else:
                            effective_content = (
                                "[内容已截断] "
                                + self.token_calculator.truncate_text_to_tokens(
                                    tr.content or "", threshold_tokens
                                )
                            )
                    flat.append(tr.model_copy(update={"content": effective_content}))

            # 工具调用结束后的模型回复（父级 assistant 消息）加入 flat
            flat.append(msg)

        return flat

    async def stream_response(
        self,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """生成完整流式响应：ack、正文流、标题（可选）、done/error。user_id 用于窗口外摘要与用户画像异步任务。"""
        conversation_id = chat_request.conversation_id
        try:
            with MessageDbService() as message_service:
                conversation, user_message, assistant_message = (
                    message_service.get_conversation_and_messages(
                        conversation_id, user_message_id, assistant_message_id
                    )
                )
                logger.debug(
                    "Retrieved conversation and messages",
                    conversation_id=conversation_id,
                    user_message_role=user_message.role,
                    assistant_message_status=assistant_message.status,
                )

                yield format_sse_message("ack", user_message)
                yield format_sse_message("ack", assistant_message)
                yield format_sse_message("refresh_conversation", conversation)

                title_task: asyncio.Task[str] | None = None
                if chat_request.regenerate_title:
                    title_task = asyncio.create_task(
                        self.generate_title(
                            chat_request.content,
                            conversation_id=conversation_id,
                        )
                    )

                raw_history = message_service.get_history_messages_by_ids(
                    chat_request.history_ids
                )
                history_messages, truncated_messages = (
                    truncate_history_by_rounds_and_tokens(
                        raw_history,
                        self.compression.max_history_rounds,
                        self.compression.max_history_tokens,
                        self.token_calculator,
                    )
                )
                # 窗口外摘要：问答开始前执行并 await，使本轮回复能使用刚生成的摘要
                if self.compression.window_out_summary_enabled and truncated_messages:
                    await _run_window_out_summary_only(
                        conversation_id=conversation_id,
                        truncated_messages=truncated_messages,
                        summary_max_tokens=self.compression.summary_max_tokens,
                    )
                new_history_messages = self.process_history_messages(history_messages)
                logger.info(
                    "Starting stream message generation",
                    conversation_id=conversation_id,
                    history_ids_count=len(chat_request.history_ids),
                    history_messages_count=len(new_history_messages),
                )

                chunk_count = 0
                async for chunk in self.stream_message(
                    chat_request=chat_request,
                    history_messages=new_history_messages,
                    client_ip=None,
                    user_id=user_id,
                    user_message_id=user_message_id,
                ):
                    if title_task is not None and title_task.done():
                        try:
                            if title_message := title_task.result():
                                yield title_message
                        except Exception:
                            pass
                        title_task = None
                    chunk_count += 1
                    yield chunk

                logger.info(
                    "Stream message generation completed",
                    conversation_id=conversation_id,
                    total_chunks=chunk_count,
                )

                assistant_payload = self.get_collected_response()
                assistant_message = message_service.update_assistant_message(
                    conversation,
                    assistant_message,
                    assistant_payload=assistant_payload,
                    status=MessageStatus.DONE,
                )

                logger.info(
                    "Assistant message updated",
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_message_id,
                    status=MessageStatus.DONE,
                    updated_at=str(assistant_message.updated_at)
                    if assistant_message.updated_at
                    else None,
                )

                done_payload = {
                    "content_length": len(assistant_payload.content),
                    "reasoning_length": len(assistant_payload.reasoning),
                    "tool_calls_length": len(assistant_payload.tool_calls),
                    "component_tool_calls_length": len(
                        assistant_payload.component_tool_calls
                    ),
                    **pick_fields(
                        assistant_payload.model_dump(mode="json"),
                        [
                            "tool_calls_duration",
                            "component_tool_calls_duration",
                            "reasoning_duration",
                            "content_duration",
                            "total_duration",
                            "token_stats",
                        ],
                    ),
                    **pick_fields(
                        assistant_message.model_dump(mode="json"), ["updated_at"]
                    ),
                }
                logger.info(
                    "Sending done message",
                    conversation_id=conversation_id,
                    **done_payload,
                )
                yield format_sse_message("done", done_payload)
                logger.info(
                    "Stream response generation completed successfully",
                    conversation_id=conversation_id,
                )

                # 用户画像：问答结束后异步执行，不阻塞响应；需助手回复内容，事实/偏好每轮都提取。
                if self.compression.window_out_summary_enabled and user_id:
                    asyncio.create_task(
                        _run_profile_extraction_only(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            user_message_content=chat_request.content,
                            assistant_content=assistant_payload.content or "",
                        ),
                        name="user_profile_extraction",
                    )
        except Exception as e:
            logger.error(
                "Error during stream response generation",
                conversation_id=conversation_id,
                error=e,
                error_type=type(e).__name__,
            )
            yield format_sse_message(
                "error",
                {"content": str(e), "conversation_id": conversation_id},
            )

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
            tool_calls=self.mcp_tools_agent.output_messages,
            component_tool_calls=self.component_tools_agent.output_messages,
            tool_calls_duration=self.mcp_tools_agent.duration,
            component_tool_calls_duration=self.component_tools_agent.duration,
            reasoning_duration=self.response_generation_agent.reasoning_duration,
            content_duration=self.response_generation_agent.content_duration,
            total_duration=self.response_generation_agent.total_duration,
            token_stats=total_token_stats.model_dump(mode="json")
            if any(
                [
                    self.mcp_tools_agent.token_stats,
                    self.component_tools_agent.token_stats,
                    self.response_generation_agent.token_stats,
                    self.title_generation_agent.token_stats,
                ]
            )
            else None,
        )
