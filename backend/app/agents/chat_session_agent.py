"""单会话 Agent：同一 messages 线程上 MCP 工具多轮 + content_blocks 流式应答。"""

from collections.abc import AsyncGenerator
from typing import Any, Literal

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.agent_skills import get_skill_registry
from app.agent_skills.types import AgentSkillManifest
from app.agents.base import BaseAgent
from app.agents.chat_session_state import (
    ChatRoundStateMachine,
    RoundState,
    SessionOutput,
)
from app.agents.mcp_tool_execution import MCPToolSession
from app.agents.utils.content_blocks import ContentBlocksAggregator
from app.agents.utils.tool_call_stream import (
    merge_tool_call_deltas,
    tool_call_acc_to_openai_list,
)
from app.core.config import settings
from app.mcp.client import MCPClientManager
from app.prompts.prompt_utils import (
    get_continue_task_notice,
    get_iteration_checkpoint_notice,
    get_summarize_task_notice,
    get_system_prompt_for_chat_session,
    get_user_message_for_tool_calls,
)
from app.protocols.chat_messages import (
    build_content_block_done_event,
    build_content_block_event,
    format_tool_call_messages_for_llm,
)
from app.schemas.chat import (
    AttachmentUploadInfo,
    ChatMessage,
    ChatRequest,
    ContentBlock,
    KbContextBlock,
)
from app.schemas.config import ChatContextConfig, LLMConfig
from app.schemas.llm import ToolMessage, ToolResultMessage
from app.schemas.user import MemorySearchItem
from app.services.chat.history_context_service import (
    HistoryContextService,
    head_tail_truncate_chars,
    tool_round_compressible_end,
)
from app.utils.date import get_current_datetime_str
from app.utils.llm_usage import log_llm_cache_usage
from app.utils.logger import logger
from app.utils.message import build_trailing_hint_user_message, update_last_user_message
from app.utils.multimodal import (
    build_user_content_for_llm,
    extract_user_text_with_attachment_placeholder,
)
from app.utils.time import get_current_time, get_time_duration

GuardAction = Literal["ok", "stop_tools"]


class ChatSessionAgent(BaseAgent):
    """合并 MCP 工具与最终应答的单会话编排。"""

    def __init__(
        self,
        think_mode: bool,
        llm_config: LLMConfig,
        mcp_manager: MCPClientManager,
        history_context_service: HistoryContextService,
        chat_context_config: ChatContextConfig | None = None,
    ):
        super().__init__(think_mode, llm_config)
        self.mcp_manager = mcp_manager
        self.history_context_service = history_context_service
        self.chat_context_config = chat_context_config or settings.chat_context
        self.session_output = SessionOutput()
        self.content_block_aggregator = ContentBlocksAggregator()
        self.content_block_aggregator.set_tool_name_resolver(mcp_manager.get_tool_route)
        self.state_machine = ChatRoundStateMachine()

        self._working_history: list[ChatMessage] = []
        self._window_out_summary: str | None = None
        self._system_prompt: str = ""
        self._agent_mode: int = 0
        self._skill_manifests: list[AgentSkillManifest] = []
        self._user_message_text: str = ""
        self._tool_guided_user_message: str = ""
        self._user_message_content: str | list[dict[str, Any]] = ""
        self._turn_datetime: str | None = None
        self._conversation_id: str | None = None

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

    @property
    def iteration_checkpoint(self) -> dict[str, int] | None:
        return self.session_output.iteration_checkpoint

    def format_sse_message(  # type: ignore[override]
        self, msg_type: str, data: dict[str, Any] | None = None
    ) -> str:
        return super().format_sse_message(msg_type, data)

    @staticmethod
    def resolve_max_tool_iterations(
        *,
        agent_mode: int,
        task_action: str | None,
    ) -> int:
        """解析本 turn 工具轮次预算。

        - agent_mode==0：固定 10（忽略 task_action）
        - agent_mode>0 + continue：50
        - agent_mode>0 其它：90
        """
        if agent_mode <= 0:
            return MCPToolSession.MAX_TOTAL_ITERATIONS
        if task_action == "continue":
            return MCPToolSession.CONTINUE_BUDGET_ITERATIONS
        return MCPToolSession.AGENT_MODE_MAX_ITERATIONS

    def _refresh_system_prompt(self) -> None:
        """Rebuild system prompt, including current window-out summary."""
        self._system_prompt = get_system_prompt_for_chat_session(
            agent_mode=self._agent_mode,
            skill_manifests=self._skill_manifests,
            window_out_summary=self._window_out_summary,
        )

    async def stream_session_events(
        self,
        *,
        chat_request: ChatRequest,
        history_messages: list[ChatMessage],
        history_summary_before_window: str | None,
        conversation_id: str,
        user_memories: list[MemorySearchItem],
        user_id: str,
        kb_context_blocks: list[KbContextBlock] | None = None,
        attachment_uploads: list[AttachmentUploadInfo] | None = None,
        current_datetime: str | None = None,
        llm_rendered_text: str | None = None,
    ) -> AsyncGenerator[str, None]:
        self.think_mode = chat_request.think_mode
        self.session_output.reset()
        self.content_block_aggregator = ContentBlocksAggregator()
        self.content_block_aggregator.set_tool_name_resolver(
            self.mcp_manager.get_tool_route
        )

        logger.info("User memories", count=len(user_memories))

        skill_manifests = (
            get_skill_registry(user_id).list_manifests()
            if chat_request.agent_mode > 0
            else []
        )
        self._agent_mode = chat_request.agent_mode
        self._skill_manifests = list(skill_manifests)
        self._window_out_summary = history_summary_before_window
        self._refresh_system_prompt()
        server_names = self._resolve_request_mcp_servers(chat_request)
        tools = await self.mcp_manager.get_tools_for_llm(
            server_names,
        )

        self._user_message_text = extract_user_text_with_attachment_placeholder(
            chat_request.content_blocks
        )
        self._working_history = list(history_messages)
        # 优先使用 user_message.created_at（编排层传入），避免记忆检索等
        # 中间步骤把 <current_datetime> 相对用户发送时刻往后推。
        self._turn_datetime = current_datetime or get_current_datetime_str()
        self._conversation_id = conversation_id

        # 编排层已固化 llm_rendered_text 时直接复用，避免重包导致与落库快照不一致。
        if llm_rendered_text and llm_rendered_text.strip():
            self._tool_guided_user_message = llm_rendered_text.strip()
        else:
            self._tool_guided_user_message = get_user_message_for_tool_calls(
                self._user_message_text,
                kb_context_blocks=kb_context_blocks,
                user_memories=user_memories,
                attachment_uploads=attachment_uploads,
                current_datetime=self._turn_datetime,
            )
        self._user_message_content = build_user_content_for_llm(
            chat_request.content_blocks,
            leading_text=self._tool_guided_user_message,
            include_text_blocks=False,
        )
        base_prompt_messages = self._compose_messages(
            self._system_prompt,
            self._working_history,
            self._user_message_content,
            [],
        )

        tool_session = MCPToolSession(
            self.mcp_manager,
            self._user_message_text,
            self.model_config.model_name,
            self.model_config.context_limit,
            self.tool_round_messages,
        )
        tool_session.reset_for_request(
            self._user_message_text,
            user_id=user_id,
            conversation_id=conversation_id,
            agent_mode=chat_request.agent_mode,
        )

        if not tools:
            action, base_prompt_messages = await self.unified_context_guard(
                base_prompt_messages=base_prompt_messages,
                conversation_id=conversation_id,
                allow_stop_tools=False,
            )
            async for sse in self._stream_final_round_events(
                messages=base_prompt_messages,
                tool_session=tool_session,
                iteration=0,
            ):
                yield sse
            return

        # Agent 模式：用户选择「到此为止」→ 跳过工具循环，基于已有内容总结
        if chat_request.agent_mode > 0 and chat_request.task_action == "summarize":
            action, base_prompt_messages = await self.unified_context_guard(
                base_prompt_messages=base_prompt_messages,
                conversation_id=conversation_id,
                allow_stop_tools=False,
            )
            async for sse in self._stream_final_round_events(
                messages=base_prompt_messages,
                tool_session=tool_session,
                iteration=0,
                extra_notice=get_summarize_task_notice(),
                extra_plugin="summarize_task",
            ):
                yield sse
            return

        tools_list = list(tools)
        max_total_iterations = self.resolve_max_tool_iterations(
            agent_mode=chat_request.agent_mode,
            task_action=chat_request.task_action,
        )
        continue_extra_notice: str | None = None
        continue_extra_plugin = "continue_task"
        if chat_request.agent_mode > 0 and chat_request.task_action == "continue":
            continue_extra_notice = get_continue_task_notice(
                continue_budget=max_total_iterations,
            )

        for iteration in range(max_total_iterations):
            action, base_prompt_messages = await self.unified_context_guard(
                base_prompt_messages=base_prompt_messages,
                conversation_id=conversation_id,
                allow_stop_tools=True,
            )
            if action == "stop_tools":
                logger.info(
                    "Unified context guard requested stop tools, "
                    "switching to final answer round",
                    iteration=iteration + 1,
                )
                async for sse in self._stream_final_round_events(
                    messages=base_prompt_messages,
                    tool_session=tool_session,
                    iteration=iteration,
                ):
                    yield sse
                return

            iteration_hints = tool_session.drain_pending_iteration_hints()
            trailing_user = build_trailing_hint_user_message(
                iteration_hints=iteration_hints,
                guardrail_warns=tool_session.drain_pending_guardrail_warns(),
                extra_notice=continue_extra_notice if iteration == 0 else None,
                extra_plugin=continue_extra_plugin,
            )
            # 续跑 notice 仅注入第一轮
            if iteration == 0:
                continue_extra_notice = None
            round_prompt_messages = self._build_round_prompt_messages(
                base_prompt_messages,
                trailing_user=trailing_user,
            )
            round_state = self.state_machine.start_round()

            async for sse in self._stream_tool_round_events(
                round_prompt_messages,
                tools_list,
                tool_session,
                iteration,
                round_state,
            ):
                yield sse

            if round_state.is_final_answer_complete:
                self._sync_session_output()
                yield build_content_block_done_event()
                return

            if tool_session.guardrail_halted:
                logger.info(
                    "Tool call guardrail halted, switching to final answer round",
                    iteration=iteration + 1,
                )
                action, base_prompt_messages = await self.unified_context_guard(
                    base_prompt_messages=base_prompt_messages,
                    conversation_id=conversation_id,
                    allow_stop_tools=False,
                )
                async for sse in self._stream_final_round_events(
                    messages=base_prompt_messages,
                    tool_session=tool_session,
                    iteration=iteration,
                ):
                    yield sse
                return

        # 触达轮次上限
        action, base_prompt_messages = await self.unified_context_guard(
            base_prompt_messages=base_prompt_messages,
            conversation_id=conversation_id,
            allow_stop_tools=False,
        )
        if chat_request.agent_mode > 0:
            logger.info(
                "Chat session max tool iterations reached, "
                "entering iteration checkpoint",
                max_iterations=max_total_iterations,
            )
            self.session_output.iteration_checkpoint = {
                "iterations_used": max_total_iterations,
                "continue_budget": MCPToolSession.CONTINUE_BUDGET_ITERATIONS,
            }
            async for sse in self._stream_final_round_events(
                messages=base_prompt_messages,
                tool_session=tool_session,
                iteration=max_total_iterations,
                extra_notice=get_iteration_checkpoint_notice(
                    iterations_used=max_total_iterations,
                ),
                extra_plugin="iteration_checkpoint",
            ):
                yield sse
            return

        logger.info(
            "Chat session max tool iterations reached, forcing final answer",
            max_iterations=max_total_iterations,
        )
        async for sse in self._stream_final_round_events(
            messages=base_prompt_messages,
            tool_session=tool_session,
            iteration=max_total_iterations,
        ):
            yield sse
        return

    async def unified_context_guard(
        self,
        *,
        base_prompt_messages: list[dict[str, Any]],
        conversation_id: str,
        allow_stop_tools: bool,
    ) -> tuple[GuardAction, list[dict[str, Any]]]:
        """每次 LLM 调用前的统一上下文守卫（分级降级）。"""
        guard = self.chat_context_config.unified_guard
        if not guard.enabled:
            logger.warning(
                "Unified context guard disabled; relying on L1 hard limit only",
                conversation_id=conversation_id,
            )
            return "ok", base_prompt_messages

        history_svc = self.history_context_service
        threshold = history_svc.compute_context_threshold(
            self.model_config.context_limit,
            self.model_config.max_output_tokens,
            guard,
        )

        def _total_tokens(base: list[dict[str, Any]]) -> int:
            return self.token_calculator.count_messages_tokens(
                self._build_round_prompt_messages(base)
            )

        total_tokens = _total_tokens(base_prompt_messages)
        if total_tokens <= threshold:
            return "ok", base_prompt_messages

        logger.info(
            "Unified context guard triggered",
            conversation_id=conversation_id,
            total_tokens=total_tokens,
            threshold=threshold,
        )

        # Step 2: compress all history tool results
        compressed_history = history_svc.compress_history_tool_results(
            self._working_history
        )
        if compressed_history is not self._working_history:
            self._working_history = compressed_history
            base_prompt_messages = self._compose_messages(
                self._system_prompt,
                self._working_history,
                self._user_message_content,
                [],
            )
            total_tokens = _total_tokens(base_prompt_messages)
            if total_tokens <= threshold:
                return "ok", base_prompt_messages

        # Step 3: window out-of-window summary by dynamic token budget
        system_tokens = self.token_calculator.count_message_tokens(
            {"role": "system", "content": self._system_prompt}
        )
        user_tokens = self.token_calculator.count_message_tokens(
            {"role": "user", "content": self._user_message_content}
        )
        tool_round_tokens = self.token_calculator.count_messages_tokens(
            format_tool_call_messages_for_llm(
                self.session_output.tool_round_messages,
                clear_reasoning_content=False,
            )
        )
        remaining_budget = threshold - system_tokens - user_tokens - tool_round_tokens
        in_window, out_of_window = history_svc.split_by_remaining_budget(
            self._working_history, remaining_budget
        )
        if out_of_window:
            summary = await history_svc.generate_window_out_summary(
                conversation_id=conversation_id,
                out_of_window_messages=out_of_window,
                prior_summary=self._window_out_summary,
            )
            if summary is not None:
                self._window_out_summary = summary
                self._refresh_system_prompt()
            self._working_history = in_window
            base_prompt_messages = self._compose_messages(
                self._system_prompt,
                self._working_history,
                self._user_message_content,
                [],
            )
            total_tokens = _total_tokens(base_prompt_messages)
            if total_tokens <= threshold:
                return "ok", base_prompt_messages

        # Step 4: size-aware compress — prefer keep_recent, then escalate to 0
        if total_tokens > threshold:
            total_tokens = self._size_aware_compress_tool_rounds(
                base_prompt_messages,
                threshold,
                keep_recent=guard.keep_recent_tool_results,
            )
        if total_tokens > threshold:
            logger.info(
                "Unified context guard Step 4 still over threshold; "
                "escalating keep_recent=0",
                conversation_id=conversation_id,
                total_tokens=total_tokens,
                threshold=threshold,
            )
            total_tokens = self._size_aware_compress_tool_rounds(
                base_prompt_messages, threshold, keep_recent=0
            )

        if total_tokens <= threshold:
            return "ok", base_prompt_messages

        if allow_stop_tools:
            logger.warning(
                "Unified context guard still over threshold after compaction; "
                "stopping tool calls",
                conversation_id=conversation_id,
                total_tokens=total_tokens,
                threshold=threshold,
            )
            return "stop_tools", base_prompt_messages

        return "ok", base_prompt_messages

    def _size_aware_compress_tool_rounds(
        self,
        base_prompt_messages: list[dict[str, Any]],
        threshold: int,
        keep_recent: int,
    ) -> int:
        """Compress largest tool results one-by-one until under threshold."""
        guard = self.chat_context_config.unified_guard
        threshold_chars = guard.tool_result_compress_threshold_chars
        keep_head = guard.tool_result_compress_keep_head_chars
        keep_tail = guard.tool_result_compress_keep_tail_chars
        messages = self.session_output.tool_round_messages
        compressible_end = tool_round_compressible_end(messages, keep_recent)
        if compressible_end <= 0:
            return self.token_calculator.count_messages_tokens(
                self._build_round_prompt_messages(base_prompt_messages)
            )

        candidates: list[int] = []
        for i in range(compressible_end):
            msg = messages[i]
            if (
                isinstance(msg, ToolResultMessage)
                and len(msg.content) > threshold_chars
            ):
                candidates.append(i)
        candidates.sort(
            key=lambda i: len(messages[i].content or ""),
            reverse=True,
        )

        total_tokens = self.token_calculator.count_messages_tokens(
            self._build_round_prompt_messages(base_prompt_messages)
        )
        for idx in candidates:
            msg = messages[idx]
            if not isinstance(msg, ToolResultMessage):
                continue
            truncated = head_tail_truncate_chars(msg.content, keep_head, keep_tail)
            if truncated == msg.content:
                continue
            msg.content = truncated
            total_tokens = self.token_calculator.count_messages_tokens(
                self._build_round_prompt_messages(base_prompt_messages)
            )
            if total_tokens <= threshold:
                break
        return total_tokens

    def _resolve_request_mcp_servers(
        self, chat_request: ChatRequest
    ) -> list[str] | None:
        if chat_request.agent_mode > 0:
            return list(settings.mcp.agent_mode_servers)
        return list(settings.mcp.normal_mode_servers)

    def _build_round_prompt_messages(
        self,
        base_messages: list[dict[str, Any]],
        *,
        trailing_user: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        formatted_collected = format_tool_call_messages_for_llm(
            self.session_output.tool_round_messages,
            clear_reasoning_content=False,
        )
        messages = base_messages + formatted_collected
        if trailing_user is not None:
            messages = messages + [trailing_user]
        return messages

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
        final_user_message: str | None = None,
        extra_notice: str | None = None,
        extra_plugin: str = "iteration_checkpoint",
    ) -> AsyncGenerator[str, None]:
        if final_user_message is not None:
            update_last_user_message(messages, new_content=final_user_message)
        # hints/warns 只服务下一轮工具循环；final 轮空 tools，带上会与终答/检查点指令冲突
        tool_session.drain_pending_iteration_hints()
        tool_session.drain_pending_guardrail_warns()
        trailing_user = build_trailing_hint_user_message(
            extra_notice=extra_notice,
            extra_plugin=extra_plugin,
        )
        round_state = self.state_machine.start_round()
        async for sse in self._stream_tool_round_events(
            self._build_round_prompt_messages(messages, trailing_user=trailing_user),
            [],
            tool_session,
            iteration,
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
        round_state: RoundState,
    ) -> AsyncGenerator[str, None]:
        self.content_block_aggregator.start_round()
        start_time = get_current_time()
        response = await self.call_llm_api(
            model=self.model_name,
            messages=round_prompt_messages,
            tools=available_tools if available_tools else None,
            stream=True,
            stream_options={"include_usage": True},
            parallel_tool_calls=True,
            extra_body=self.extra_body,
        )

        tool_call_deltas_by_index: dict[int, dict[str, Any]] = {}
        accumulated_reasoning = ""
        accumulated_content = ""
        finish_reason: str | None = None
        stream_usage: Any = None

        async for chunk in response:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                stream_usage = chunk_usage
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

        log_llm_cache_usage(
            stream_usage,
            model=self.model_name,
            conversation_id=self._conversation_id,
            iteration=iteration,
        )

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

        assistant_tool_use_message = tool_session.build_tool_use_message(
            tool_calls_fc,
            accumulated_content,
            accumulated_reasoning or None,
        )
        self.session_output.tool_round_messages.append(assistant_tool_use_message)

        tool_result_messages = await tool_session.execute_tool_calls_parallel(
            tool_calls_fc,
            iteration,
        )
        self.state_machine.begin_finalizing()
        for tool_result_message in tool_result_messages:
            self.session_output.tool_round_messages.append(tool_result_message)
            yield build_content_block_event(
                self.content_block_aggregator.append_tool_result(tool_result_message)
            )
        self._sync_session_output()
