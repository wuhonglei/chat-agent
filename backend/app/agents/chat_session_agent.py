"""单会话 Agent：同一 messages 线程上 MCP 工具多轮 + content_blocks 流式应答。"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.agents.base import BaseAgent
from app.agents.mcp_tool_execution import MCPToolSession, get_mcp_server_names
from app.agents.utils.content_blocks import ContentBlocksAggregator
from app.agents.utils.tool_call_stream import (
    merge_tool_call_deltas,
    tool_call_acc_to_openai_list,
)
from app.mcp.mcp_client import MCPClientManager
from app.prompts import (
    get_merged_system_prompt_for_chat_session,
    get_user_message_for_no_tool_call,
    get_user_message_for_tool_calls,
)
from app.schemas.chat import (
    ChatMessageItem,
    ChatRequest,
    ContentBlock,
    extract_user_text,
)
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolMessage
from app.schemas.user import MemoryListItem
from app.utils.logger import logger
from app.utils.message import (
    format_tool_call_messages_for_llm,
    update_last_user_message,
)
from app.utils.time import get_current_time, get_time_duration


@dataclass
class _RoundState:
    final_answer_done: bool = False


class ChatSessionAgent(BaseAgent):
    """合并 MCP 工具与最终应答的单会话编排。"""

    def __init__(
        self,
        think_mode: bool,
        llm_config: LLMConfig,
        mcp_manager: MCPClientManager,
    ):
        super().__init__(think_mode, llm_config)
        self.mcp_manager = mcp_manager
        self.output_messages: list[ToolMessage] = []
        self.content_blocks: list[ContentBlock] = []
        self.content = ""
        self.reasoning = ""
        self.blocks_aggregator = ContentBlocksAggregator()

    def format_sse_message(  # type: ignore[override]
        self, msg_type: str, data: dict[str, Any] | None = None
    ) -> str:
        return super().format_sse_message(msg_type, data)

    async def stream_execute(  # type: ignore[override]
        self,
        *,
        chat_request: ChatRequest,
        history_messages: list[ChatMessageItem],
        client_ip: str | None,
        window_out_summary: str | None,
        user_id: str,
        conversation_id: str,
        user_memories: list[MemoryListItem],
    ) -> AsyncGenerator[str, None]:
        _ = user_id
        _ = conversation_id
        self.think_mode = chat_request.think_mode
        self.output_messages = []
        self.content_blocks = []
        self.content = ""
        self.reasoning = ""
        self.blocks_aggregator = ContentBlocksAggregator()

        user_message = extract_user_text(chat_request.content_blocks)
        memories = [m.memory for m in user_memories]
        logger.info("User memories", count=len(memories), memories=memories)

        system_prompt = get_merged_system_prompt_for_chat_session(
            user_memories=memories,
            window_out_summary=window_out_summary,
        )
        server_names = get_mcp_server_names(
            chat_request.mcp_auto_mode, chat_request.source_config
        )
        tools = await self.mcp_manager.get_tools_for_llm(
            server_names,
            client_ip,
        )

        tool_call_user_message = get_user_message_for_tool_calls(
            user_message,
            chat_request.mcp_auto_mode,
            server_names or [],
            client_ip,
        )
        messages = self._compose_messages(
            system_prompt, history_messages, tool_call_user_message, []
        )

        tool_ctx = MCPToolSession(
            self.mcp_manager,
            user_message,
            self.output_messages,
        )
        tool_ctx.reset_for_request(user_message)

        if not tools:
            update_last_user_message(
                messages,
                new_content=get_user_message_for_no_tool_call(user_message),
            )
            state = _RoundState()
            async for sse in self._stream_one_round_with_tools(
                messages,
                [],
                tool_ctx,
                iteration=0,
                iterations_by_tool={},
                state=state,
            ):
                yield sse
            self._sync_collected_content()
            yield self.format_sse_message("content_block", {"op": "done"})
            return

        tools_list = list(tools)
        iterations_by_tool: dict[str, int] = {
            t["function"]["name"]: tool_ctx.MAX_ITERATIONS_BY_TOOL for t in tools_list
        }

        for iteration in range(tool_ctx.MAX_TOTAL_ITERATIONS):
            tool_ctx._update_user_message_with_tool_hints(
                messages=messages,
                tools=tools_list,
                iterations_by_tool=iterations_by_tool,
                tool_call_user_message=tool_call_user_message,
                iteration=iteration,
            )
            available_tools, _ = tool_ctx._get_tools_state(
                tools_list, iterations_by_tool
            )
            formatted_collected = format_tool_call_messages_for_llm(
                self.output_messages,
                clear_reasoning_content=False,
            )
            llm_messages = messages + formatted_collected
            state = _RoundState()

            async for sse in self._stream_one_round_with_tools(
                llm_messages,
                available_tools,
                tool_ctx,
                iteration,
                iterations_by_tool,
                state,
            ):
                yield sse

            if state.final_answer_done:
                self._sync_collected_content()
                yield self.format_sse_message("content_block", {"op": "done"})
                return

        logger.info(
            "Chat session max tool iterations reached",
            max_iterations=tool_ctx.MAX_TOTAL_ITERATIONS,
        )

        return

    def _sync_collected_content(self) -> None:
        self.content_blocks = list(self.blocks_aggregator.blocks)
        self.content = self.blocks_aggregator.get_content()
        self.reasoning = self.blocks_aggregator.get_reasoning()

    async def _stream_one_round_with_tools(
        self,
        llm_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        tool_ctx: MCPToolSession,
        iteration: int,
        iterations_by_tool: dict[str, int],
        state: _RoundState,
    ) -> AsyncGenerator[str, None]:
        start_time = get_current_time()
        response = await self.call_llm_api(
            model=self.model_name,
            messages=llm_messages,
            tools=available_tools if available_tools else None,
            stream=True,
            parallel_tool_calls=True,
            extra_body=self.extra_body,
        )

        tool_acc: dict[int, dict[str, Any]] = {}
        full_reasoning = ""
        full_content = ""
        finish_reason: str | None = None

        async for chunk in response:
            if not chunk.choices:
                continue
            choice0 = chunk.choices[0]
            if choice0.finish_reason:
                finish_reason = choice0.finish_reason
            delta = getattr(choice0, "delta", None)
            if not delta:
                continue

            d_tool_calls = getattr(delta, "tool_calls", None)
            if d_tool_calls:
                merge_tool_call_deltas(tool_acc, d_tool_calls)
                for event in self.blocks_aggregator.process_tool_call_deltas(
                    d_tool_calls
                ):
                    yield self.format_sse_message("content_block", event)

            rc = getattr(delta, "reasoning_content", None)
            if rc:
                full_reasoning += rc
                for event in self.blocks_aggregator.append_thinking_delta(rc):
                    yield self.format_sse_message("content_block", event)

            ct = getattr(delta, "content", None)
            if ct:
                full_content += ct
                for event in self.blocks_aggregator.append_text_delta(ct):
                    yield self.format_sse_message("content_block", event)

        merged_tool_calls = tool_call_acc_to_openai_list(tool_acc)
        has_tool_calls = bool(merged_tool_calls) or finish_reason == "tool_calls"

        if finish_reason == "tool_calls" and not merged_tool_calls:
            logger.warning(
                "Stream finished with tool_calls but empty aggregated tool_calls; "
                "falling back to buffered text",
                finish_reason=finish_reason,
            )
            has_tool_calls = False

        if not has_tool_calls:
            self._sync_collected_content()
            state.final_answer_done = True
            logger.info(
                "Stream tool round: final answer (no tool_calls)",
                duration=get_time_duration(start_time),
            )
            return

        tool_calls_fc: list[ChatCompletionMessageFunctionToolCall] = merged_tool_calls
        yield self.format_sse_message(
            "content_block", self.blocks_aggregator.finalize_round()
        )
        tool_ctx._should_continue_tool_calls(tool_calls_fc)

        assistant_message = tool_ctx.build_tool_use_message(
            tool_calls_fc,
            full_content,
            full_reasoning or None,
        )
        self.output_messages.append(assistant_message)

        tool_results = await tool_ctx._execute_tool_calls_parallel(
            tool_calls_fc,
            iteration,
            iterations_by_tool,
        )
        for tool_result_message in tool_results:
            self.output_messages.append(tool_result_message)
            yield self.format_sse_message(
                "content_block",
                self.blocks_aggregator.append_tool_result(tool_result_message),
            )
        self._sync_collected_content()
