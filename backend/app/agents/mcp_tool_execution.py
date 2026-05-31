"""MCP tool session composed from policy and executor helpers."""

from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.agents.tool_call_policy import ToolCallPolicy
from app.agents.tool_executor import ToolExecutor
from app.mcp.client import MCPClientManager
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage


class MCPToolSession:
    """单次请求内的 MCP 工具状态与执行逻辑。"""

    MAX_TOTAL_ITERATIONS = 10
    AGENT_MODE_MAX_ITERATIONS = 90

    def __init__(
        self,
        mcp_manager: MCPClientManager,
        user_message: str,
        model_name: str,
        tool_round_messages: list[ToolMessage],
    ):
        self.mcp_manager = mcp_manager
        self.tool_round_messages = tool_round_messages
        self.policy = ToolCallPolicy(tool_round_messages)
        self.executor = ToolExecutor(mcp_manager, user_message, model_name)

    def reset_for_request(
        self,
        user_message: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        self.policy.reset_for_request()
        self.executor.reset_for_request(user_message, user_id, conversation_id)

    def apply_iteration_hints(
        self,
        messages: list[dict[str, Any]],
        tool_guided_user_message: str,
        iteration: int,
    ) -> None:
        self.policy.apply_iteration_hints(
            messages=messages,
            tool_guided_user_message=tool_guided_user_message,
            iteration=iteration,
        )

    def should_continue_rounds(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall] | None
    ) -> tuple[bool, str | None]:
        return self.policy.should_continue(tool_calls)

    async def execute_tool_calls_parallel(
        self,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        current_iteration: int,
    ) -> list[ToolResultMessage]:
        return await self.executor.execute_tool_calls_parallel(
            tool_calls=tool_calls,
            current_iteration=current_iteration,
            extracted_urls=self.policy.extracted_urls,
            on_arguments_recorded=self.policy.record_tool_arguments,
            on_urls_extracted=self.policy.track_extracted_urls,
        )

    def build_tool_use_message(
        self,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        content: str,
        reasoning_content: str | None,
    ) -> ToolUseMessage:
        return ToolUseMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content or None,
        )
