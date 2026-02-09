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
from app.prompts import get_user_message_combine_tool_calls
from app.schemas.chat import (
    ChatMessageItem,
    ChatRequest,
    CollectedResponse,
    MessageStatus,
)
from app.schemas.config import ChatContextConfig
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.schemas.token_stats import TotalTokenStats
from app.schemas.user import MemoryListItem
from app.services.component import ComponentSchemaService
from app.services.conversation import (
    ContextSummaryService,
    ConversationContextDbService,
)
from app.services.message import MessageDbService
from app.services.user.memory_service import MemoryService
from app.utils.common import pick_fields
from app.utils.history_truncate import truncate_history_by_rounds_and_tokens
from app.utils.logger import logger
from app.utils.message import (
    filter_tool_call_messages,
    format_tool_call_messages_for_llm,
)
from app.utils.model import format_sse_message
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator


def _truncated_set_ids(truncated_messages: list[ChatMessageItem]) -> list[str]:
    """当前截断消息的 id 列表（稳定排序），用于写入 last_summarized_message_ids。"""
    return sorted(m.id for m in truncated_messages)


async def _run_window_out_summary_only(
    conversation_id: str,
    truncated_messages: list[ChatMessageItem] | None,
    summary_max_tokens: int,
    *,
    new_summary: str | None = None,
    truncated_set_ids: list[str] | None = None,
) -> str | None:
    """仅做窗口外摘要并写入 summary_before_window 与 last_summarized_message_ids；全量或增量由参数区分。
    - 全量：传入 truncated_messages，内部调用 summarize_truncated_messages，再 upsert。
    - 增量：传入 new_summary + truncated_set_ids，仅 upsert。
    """
    if new_summary is not None and truncated_set_ids is not None:
        logger.info(
            "Running window-out summary upsert (incremental)",
            conversation_id=conversation_id,
        )
        try:
            with ConversationContextDbService() as ctx_svc:
                context = ctx_svc.upsert_conversation_context(
                    conversation_id,
                    summary_before_window=new_summary,
                    last_summarized_message_ids=truncated_set_ids,
                )
                return context.summary_before_window
        except Exception as e:
            logger.warning(
                "Window-out summary upsert failed",
                conversation_id=conversation_id,
                error=e,
            )
        return None

    if not truncated_messages:
        return None

    logger.info(
        "Running window-out summary (full)",
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
                context = ctx_svc.upsert_conversation_context(
                    conversation_id,
                    summary_before_window=summary,
                    last_summarized_message_ids=truncated_set_ids,
                )
                return context.summary_before_window
        return None
    except Exception as e:
        logger.warning(
            "Window-out summary task failed",
            conversation_id=conversation_id,
            error=e,
        )
        return None


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(
        self,
        think_mode: bool,
        mcp_manager: MCPClientManager,
        chat_context_config: ChatContextConfig,
    ):
        self.debug = settings.app.debug
        self.chat_context_config = chat_context_config
        self.history_window_config = self.chat_context_config.history_window
        self.window_out_summary_config = self.chat_context_config.window_out_summary
        self.memory_service = MemoryService(self.chat_context_config.memory_config)
        self.schema_service = ComponentSchemaService(debug=self.debug)

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
        window_out_summary: str | None,
        history_messages: list[ChatMessageItem],
        user_id: str,
        client_ip: str | None,
        user_memories: list[MemoryListItem] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response using agent architecture. user_memories 由上层 Mem0 搜索得到后传入。"""
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
                window_out_summary=window_out_summary,
                history_messages=history_messages,
                user_message=user_message,
                mcp_tool_call_messages=filtered_mcp_tool_call_messages,
                component_tool_call_messages=filtered_component_tool_call_messages,
                user_id=user_id,
                conversation_id=chat_request.conversation_id,
                user_memories=user_memories or [],
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
    ) -> list[ChatMessageItem]:
        """
        处理对话历史：最后 2 条视为最后一轮（完整 tool 消息），其他轮用 summary/content/截断参与组装。
        返回扁平列表，供 _compose_messages 按条 format_chat_message_for_llm。
        """
        if not history_messages:
            return []

        threshold_tokens = self.chat_context_config.tool_result_compression.message_summary_threshold_tokens

        # 最后一轮简单视为 history_messages 的最后 2 条
        last_round_start = max(0, len(history_messages) - 2)

        flat: list[ChatMessageItem] = []

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
            tool_calls: list[ToolCallMessage] = []
            for m in tool_calls_list:
                if getattr(m, "role", None) == "assistant":
                    tool_calls.append(cast(AssistantToolCallMessage, m))
                elif getattr(m, "role", None) == "tool":
                    tr = cast(ToolCallResultMessage, m)
                    if is_latest_tool_round:
                        tool_calls.append(tr)
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
                    tool_calls.append(
                        tr.model_copy(update={"content": effective_content})
                    )

            tool_items = format_tool_call_messages_for_llm(
                tool_calls, clear_reasoning_content=True
            )

            last_message = flat[-1] if flat else None
            if last_message and last_message.role == "user":
                # 工具调用结束后的模型回复（父级 assistant 消息）加入 flat
                last_message.content = get_user_message_combine_tool_calls(
                    last_message.content or "",
                    tool_items,
                    [],  # 历史消息不拼接组件数据
                )
            flat.append(msg)

        return flat

    async def prepare_history_messages(
        self,
        raw_history: list[ChatMessageItem],
        conversation_id: str,
    ) -> tuple[str | None, list[ChatMessageItem]]:
        """
        处理对话历史：截断轮次与 token、可选窗口外摘要、再扁平化为带 tool_calls 的消息列表。
        供 stream_response 等调用方在获取 raw_history 后使用。
        """
        history_messages, truncated_messages = truncate_history_by_rounds_and_tokens(
            raw_history,
            self.history_window_config.max_rounds,
            self.history_window_config.max_tokens,
            self.token_calculator,
        )
        window_out_summary = None
        if self.window_out_summary_config.enabled and truncated_messages:
            current_ids = _truncated_set_ids(truncated_messages)
            with ConversationContextDbService() as ctx_svc:
                ctx = ctx_svc.get_conversation_context(conversation_id)
                window_out_summary = ctx.summary_before_window if ctx else None
            last_ids: list[str] = (
                list(ctx.last_summarized_message_ids or []) if ctx else []
            )
            if sorted(current_ids) == sorted(last_ids):
                return window_out_summary, self.process_history_messages(
                    history_messages
                )
            delta_ids = set(current_ids) - set(last_ids)
            summary_max_tokens = self.window_out_summary_config.summary_max_tokens
            if (
                set[str](last_ids) <= set(current_ids)
                and delta_ids
                and ctx
                and (ctx.summary_before_window or "").strip()
            ):
                delta_messages = [m for m in truncated_messages if m.id in delta_ids]
                summary_svc = ContextSummaryService()
                new_summary = await summary_svc.summarize_merge(
                    ctx.summary_before_window or "",
                    delta_messages,
                    max_tokens=summary_max_tokens,
                )
                if new_summary:
                    window_out_summary = await _run_window_out_summary_only(
                        conversation_id=conversation_id,
                        truncated_messages=None,
                        summary_max_tokens=summary_max_tokens,
                        new_summary=new_summary,
                        truncated_set_ids=current_ids,
                    )
            else:
                window_out_summary = await _run_window_out_summary_only(
                    conversation_id=conversation_id,
                    truncated_messages=truncated_messages,
                    summary_max_tokens=summary_max_tokens,
                    truncated_set_ids=current_ids,
                )
        return window_out_summary, self.process_history_messages(history_messages)

    async def stream_response(
        self,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str,
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
                (
                    window_out_summary,
                    new_history_messages,
                ) = await self.prepare_history_messages(raw_history, conversation_id)
                logger.info(
                    "Starting stream message generation",
                    conversation_id=conversation_id,
                    history_ids_count=len(chat_request.history_ids),
                    history_messages_count=len(new_history_messages),
                )

                user_memory_texts = await self.memory_service.search(
                    query=chat_request.content,
                    user_id=user_id,
                )

                chunk_count = 0
                async for chunk in self.stream_message(
                    chat_request=chat_request,
                    window_out_summary=window_out_summary,
                    history_messages=new_history_messages,
                    client_ip=None,
                    user_id=user_id,
                    user_memories=user_memory_texts,
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

                # Mem0 记忆：问答结束后异步写入，不阻塞响应
                asyncio.create_task(
                    self.memory_service.add_memories(
                        messages=[
                            {"role": "user", "content": chat_request.content},
                            {
                                "role": "assistant",
                                "content": assistant_payload.content or "",
                            },
                        ],
                        user_id=user_id,
                    ),
                    name="mem0_add_memories",
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
