"""单会话 Agent：同一 messages 线程上 MCP 工具多轮 + content_blocks 流式应答。"""

from collections.abc import AsyncGenerator
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.agents.base import BaseAgent
from app.agents.chat_session_state import (
    ChatRoundStateMachine,
    RoundState,
    SessionOutput,
)
from app.agents.mcp_tool_execution import (
    MCPToolSession,
    resolve_enabled_mcp_servers,
)
from app.agents.utils.content_blocks import ContentBlocksAggregator
from app.agents.utils.tool_call_stream import (
    merge_tool_call_deltas,
    tool_call_acc_to_openai_list,
)
from app.mcp.mcp_client import MCPClientManager
from app.prompts import (
    get_merged_system_prompt_for_chat_session,
    get_user_message_for_tool_calls,
)
from app.protocols.chat_messages import (
    build_content_block_done_event,
    build_content_block_event,
    format_tool_call_messages_for_llm,
)
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ContentBlock,
)
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolMessage
from app.schemas.user import MemoryListItem
from app.utils.logger import logger
from app.utils.message import update_last_user_message
from app.utils.multimodal import (
    build_user_content_for_llm,
    extract_user_text_with_attachment_placeholder,
)
from app.utils.time import get_current_time, get_time_duration


class ChatSessionAgent(BaseAgent):
    """合并 MCP 工具与最终应答的单会话编排。"""

    def __init__(
        self,
        think_mode: bool,
        llm_config: LLMConfig,
        mcp_manager: MCPClientManager,
        tool_context_limit_ratio: float = 0.8,
    ):
        super().__init__(think_mode, llm_config)
        self.mcp_manager = mcp_manager
        self.session_output = SessionOutput()
        self.content_block_aggregator = ContentBlocksAggregator()
        self.state_machine = ChatRoundStateMachine()
        self.tool_context_limit_ratio = tool_context_limit_ratio

    @property
    def tool_round_messages(self) -> list[ToolMessage]:
        return self.session_output.tool_round_messages

    @property
    def content_blocks(self) -> list[ContentBlock]:
        return self.session_output.content_blocks

    @property
    def content(self) -> str:
        return self.session_output.content

    @property
    def reasoning(self) -> str:
        return self.session_output.reasoning

    def format_sse_message(  # type: ignore[override]
        self, msg_type: str, data: dict[str, Any] | None = None
    ) -> str:
        return super().format_sse_message(msg_type, data)

    async def stream_session_events(
        self,
        *,
        chat_request: ChatRequest,
        history_messages: list[ChatMessage],
        client_ip: str | None,
        history_summary_before_window: str | None,
        user_id: str,
        conversation_id: str,
        user_memories: list[MemoryListItem],
    ) -> AsyncGenerator[str, None]:
        _ = user_id
        _ = conversation_id
        self.think_mode = chat_request.think_mode
        self.session_output.reset()
        self.content_block_aggregator = ContentBlocksAggregator()

        memories = [m.memory for m in user_memories]
        logger.info("User memories", count=len(memories), memories=memories)

        system_prompt = get_merged_system_prompt_for_chat_session(
            user_memories=memories,
            window_out_summary=history_summary_before_window,
        )
        server_names = resolve_enabled_mcp_servers(
            chat_request.mcp_auto_mode, chat_request.source_config
        )
        tools = await self.mcp_manager.get_tools_for_llm(
            server_names,
            client_ip,
        )

        user_message_text = extract_user_text_with_attachment_placeholder(
            chat_request.content_blocks
        )
        tool_guided_user_message = get_user_message_for_tool_calls(
            user_message_text,
            chat_request.mcp_auto_mode,
            server_names or [],
            client_ip,
        )
        user_message_content = build_user_content_for_llm(
            chat_request.content_blocks,
            leading_text=tool_guided_user_message,
            include_text_blocks=False,
        )
        base_prompt_messages = self._compose_messages(
            system_prompt, history_messages, user_message_content, []
        )

        tool_session = MCPToolSession(
            self.mcp_manager,
            user_message_text,
            self.tool_round_messages,
        )
        tool_session.reset_for_request(user_message_text)

        if not tools:
            async for sse in self._stream_final_round_events(
                messages=base_prompt_messages,
                tool_session=tool_session,
                iteration=0,
                iterations_by_tool={},
            ):
                yield sse
            return

        tools_list = list(tools)
        iterations_by_tool: dict[str, int] = {
            t["function"]["name"]: tool_session.MAX_ITERATIONS_BY_TOOL
            for t in tools_list
        }

        for iteration in range(tool_session.MAX_TOTAL_ITERATIONS):
            tool_session.apply_iteration_hints(
                messages=base_prompt_messages,
                tools=tools_list,
                iterations_by_tool=iterations_by_tool,
                tool_guided_user_message=tool_guided_user_message,
                iteration=iteration,
            )
            available_tools, _ = tool_session.get_available_tools(
                tools_list, iterations_by_tool
            )
            round_prompt_messages = self._build_round_prompt_messages(
                base_prompt_messages
            )
            round_state = self.state_machine.start_round()

            async for sse in self._stream_tool_round_events(
                round_prompt_messages,
                available_tools,
                tool_session,
                iteration,
                iterations_by_tool,
                round_state,
            ):
                yield sse

            if round_state.is_final_answer_complete:
                self._sync_session_output()
                yield build_content_block_done_event()
                return

            if self._check_round_context_budget(
                self._build_round_prompt_messages(base_prompt_messages)
            )[0]:
                logger.info(
                    "Tool context limit reached, switching to final answer round",
                    iteration=iteration + 1,
                )
                async for sse in self._stream_final_round_events(
                    messages=base_prompt_messages,
                    tool_session=tool_session,
                    iteration=iteration,
                    iterations_by_tool=iterations_by_tool,
                ):
                    yield sse
                return

        logger.info(
            "Chat session max tool iterations reached, forcing final answer",
            max_iterations=tool_session.MAX_TOTAL_ITERATIONS,
        )
        async for sse in self._stream_final_round_events(
            messages=base_prompt_messages,
            tool_session=tool_session,
            iteration=tool_session.MAX_TOTAL_ITERATIONS,
            iterations_by_tool=iterations_by_tool,
        ):
            yield sse
        return

    def _build_round_prompt_messages(
        self, base_messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        formatted_collected = format_tool_call_messages_for_llm(
            self.session_output.tool_round_messages,
            clear_reasoning_content=False,
        )
        return base_messages + formatted_collected

    def _check_round_context_budget(
        self, next_round_messages: list[dict[str, Any]]
    ) -> tuple[bool, int, int]:
        current_tokens = self.token_calculator.count_messages_tokens(
            next_round_messages
        )
        threshold_tokens = int(self.model_limit * self.tool_context_limit_ratio)
        is_over_threshold = current_tokens > threshold_tokens
        if is_over_threshold:
            logger.warning(
                "Tool round context budget exceeded",
                current_tokens=current_tokens,
                threshold_tokens=threshold_tokens,
                model_limit=self.model_limit,
                threshold_ratio=self.tool_context_limit_ratio,
            )
        return is_over_threshold, current_tokens, threshold_tokens

    def _sync_session_output(self) -> None:
        self.session_output.content_blocks = list(self.content_block_aggregator.blocks)
        self.session_output.content = self.content_block_aggregator.get_content()
        self.session_output.reasoning = self.content_block_aggregator.get_reasoning()

    async def _stream_final_round_events(
        self,
        *,
        messages: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        iterations_by_tool: dict[str, int],
        final_user_message: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if final_user_message is not None:
            update_last_user_message(messages, new_content=final_user_message)
        round_state = self.state_machine.start_round()
        async for sse in self._stream_tool_round_events(
            self._build_round_prompt_messages(messages),
            [],
            tool_session,
            iteration,
            iterations_by_tool,
            round_state,
        ):
            yield sse
        self._sync_session_output()
        yield build_content_block_done_event()

    async def _stream_tool_round_events(
        self,
        round_prompt_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        iterations_by_tool: dict[str, int],
        round_state: RoundState,
    ) -> AsyncGenerator[str, None]:
        self.content_block_aggregator.start_round()
        start_time = get_current_time()
        response = await self.call_llm_api(
            model=self.model_name,
            messages=round_prompt_messages,
            tools=available_tools if available_tools else None,
            stream=True,
            parallel_tool_calls=True,
            extra_body=self.extra_body,
        )

        tool_call_deltas_by_index: dict[int, dict[str, Any]] = {}
        accumulated_reasoning = ""
        accumulated_content = ""
        finish_reason: str | None = None

        async for chunk in response:
            if not chunk.choices:
                continue
            first_choice = chunk.choices[0]
            if first_choice.finish_reason:
                finish_reason = first_choice.finish_reason
            delta = getattr(first_choice, "delta", None)
            if not delta:
                continue

            d_tool_calls = getattr(delta, "tool_calls", None)
            if d_tool_calls:
                merge_tool_call_deltas(tool_call_deltas_by_index, d_tool_calls)
                for event in self.content_block_aggregator.process_tool_call_deltas(
                    d_tool_calls
                ):
                    yield build_content_block_event(event)

            reasoning_delta = getattr(delta, "reasoning_content", None)
            if reasoning_delta:
                accumulated_reasoning += reasoning_delta
                for event in self.content_block_aggregator.append_thinking_delta(
                    reasoning_delta
                ):
                    yield build_content_block_event(event)

            content_delta = getattr(delta, "content", None)
            if content_delta:
                accumulated_content += content_delta
                for event in self.content_block_aggregator.append_text_delta(
                    content_delta
                ):
                    yield build_content_block_event(event)

        merged_tool_calls = tool_call_acc_to_openai_list(tool_call_deltas_by_index)
        has_tool_calls = bool(merged_tool_calls) or finish_reason == "tool_calls"

        if finish_reason == "tool_calls" and not merged_tool_calls:
            logger.warning(
                "Stream finished with tool_calls but empty aggregated tool_calls; "
                "falling back to buffered text",
                finish_reason=finish_reason,
            )
            has_tool_calls = False

        if not has_tool_calls:
            self.state_machine.mark_done()
            self._sync_session_output()
            round_state.is_final_answer_complete = True
            logger.info(
                "Stream tool round: final answer (no tool_calls)",
                duration=get_time_duration(start_time),
            )
            return

        tool_calls_fc: list[ChatCompletionMessageFunctionToolCall] = merged_tool_calls
        self.state_machine.begin_tool_calling()
        yield build_content_block_event(self.content_block_aggregator.finalize_round())
        tool_session.should_continue_rounds(tool_calls_fc)

        assistant_tool_use_message = tool_session.build_tool_use_message(
            tool_calls_fc,
            accumulated_content,
            accumulated_reasoning or None,
        )
        self.session_output.tool_round_messages.append(assistant_tool_use_message)

        tool_result_messages = await tool_session.execute_tool_calls_parallel(
            tool_calls_fc,
            iteration,
            iterations_by_tool,
        )
        self.state_machine.begin_finalizing()
        for tool_result_message in tool_result_messages:
            self.session_output.tool_round_messages.append(tool_result_message)
            yield build_content_block_event(
                self.content_block_aggregator.append_tool_result(tool_result_message)
            )
        self._sync_session_output()
