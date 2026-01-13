"""Response Generation Agent for generating final chat responses"""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from app.agents.base import BaseAgent
from app.prompts import get_default_system_prompt
from app.prompts.prompt_utils import get_user_message_with_component_data
from app.schemas.chat import ChatMessageItemReq
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolCallMessage
from app.schemas.token_stats import ResponseGenerationTokenStats
from app.services.component_schema_service import ComponentSchemaService
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


class ResponseGenerationAgent(BaseAgent):
    """响应生成Agent - 负责生成最终的聊天响应"""

    def __init__(
        self,
        think_mode: bool,
        llm_config: LLMConfig,
        schema_service: ComponentSchemaService,
    ):
        super().__init__(think_mode, llm_config)
        self.content = ""
        self.reasoning = ""
        self.schema_service = schema_service
        self.reasoning_duration: float | None = None
        self.content_duration: float | None = None
        self.total_duration: float | None = None
        self.token_stats: ResponseGenerationTokenStats | None = None

    def format_sse_message(
        self, msg_type: str, data: dict[str, Any] | None = None
    ) -> str:
        """格式化SSE消息，并更新状态（如果需要）"""
        if msg_type == "content":
            self.content += data.get("content") or ""
        elif msg_type == "reasoning":
            self.reasoning += data.get("content") or ""
        return super().format_sse_message(msg_type, data)

    async def stream_execute(
        self,
        history: list[ChatMessageItemReq],
        user_message: str,
        mcp_tool_call_messages: list[ToolCallMessage],
        component_tool_call_messages: list[ToolCallMessage],
    ) -> AsyncGenerator[str, None]:
        """
        流式生成最终响应

        Args:
            history: 对话历史
            user_message: 原始用户消息
            mcp_tool_call_messages: MCP工具调用消息
            component_tool_call_messages: 组件工具调用消息

        Yields:
            str: SSE格式的响应消息
        """
        # 将组件数据拼接到 user_message
        final_user_message = get_user_message_with_component_data(
            user_message,
            component_tool_call_messages,
            self.schema_service.get_schema_cache(),
        )

        system_prompt = get_default_system_prompt(include_date=False)
        new_messages = self._compose_messages(
            system_prompt, history, final_user_message, mcp_tool_call_messages
        )

        async for chunk in self._stream_final_response(
            new_messages, self.model_name, self.extra_body
        ):
            yield chunk

        # 创建 token 统计对象（内部进行所有 token 计算）
        self.token_stats = self.create_token_stats(
            input_messages=new_messages, reasoning=self.reasoning, content=self.content
        )

    def _finish_streaming_type(
        self,
        msg_type: str,
        start_time: float,
        fallback_content: str = "",
    ) -> str:
        """结束某个类型的流式输出并返回 done 消息"""
        duration = get_time_duration(start_time)
        if msg_type == "reasoning":
            self.reasoning_duration = duration
        elif msg_type == "content":
            self.content_duration = duration

        return self.format_sse_message(
            msg_type,
            {
                "status": "done",
                "content": fallback_content,
                "duration": duration,
            },
        )

    async def _stream_final_response(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream final response

        模型返回内容只有2种情况：
        1. 只有 content
        2. 先有 reasoning_content，结束后才会有 content
        """
        start_time = get_current_time()
        response = await self._call_llm_api(
            model=model,
            messages=messages,
            stream=True,
            extra_body=extra_body,
        )

        # 状态追踪：None -> 'reasoning' -> 'content' 或 None -> 'content'
        current_phase = None  # None, 'reasoning', 'content'
        phase_start_time = None

        async for chunk in response:
            if not chunk.choices or not getattr(chunk.choices[0], "delta", None):
                continue

            delta = chunk.choices[0].delta
            reasoning_content = getattr(delta, "reasoning_content", None)
            content = getattr(delta, "content", None)

            # 处理推理内容
            if reasoning_content:
                if current_phase != "reasoning":
                    # 开始推理阶段
                    current_phase = "reasoning"
                    phase_start_time = get_current_time()
                    yield self.format_sse_message(
                        "reasoning",
                        {
                            "status": "start",
                            "content": reasoning_content,
                        },
                    )
                else:
                    # 继续推理阶段
                    yield self.format_sse_message(
                        "reasoning",
                        {
                            "status": "continue",
                            "content": reasoning_content,
                        },
                    )

            # 处理实际内容
            if content:
                if current_phase == "reasoning":
                    # 从推理阶段切换到内容阶段：先结束推理
                    yield self._finish_streaming_type("reasoning", phase_start_time)
                    current_phase = "content"
                    phase_start_time = get_current_time()
                    yield self.format_sse_message(
                        "content",
                        {
                            "status": "start",
                            "content": content,
                        },
                    )
                elif current_phase != "content":
                    # 直接开始内容阶段（没有推理）
                    current_phase = "content"
                    phase_start_time = get_current_time()
                    yield self.format_sse_message(
                        "content",
                        {
                            "status": "start",
                            "content": content,
                        },
                    )
                else:
                    # 继续内容阶段
                    yield self.format_sse_message(
                        "content",
                        {
                            "status": "continue",
                            "content": content,
                        },
                    )

        # 收尾：结束当前仍在进行的阶段
        if current_phase == "reasoning":
            # 情况2：只有推理，没有内容
            yield self._finish_streaming_type("reasoning", phase_start_time)
            # 发送占位消息，确保前端感知到内容结束
            yield self._finish_streaming_type(
                "content", get_current_time(), "[模型已完成深入推理，详见思考过程]"
            )
        elif current_phase == "content":
            # 情况1或情况2：有内容（可能之前有推理，可能没有）
            yield self._finish_streaming_type("content", phase_start_time)

        self.total_duration = get_time_duration(start_time)
        logger.info("Stream final response completed", duration=self.total_duration)

    def create_token_stats(
        self,
        input_messages: list[dict],
        reasoning: str,
        content: str,
    ) -> ResponseGenerationTokenStats:
        """创建响应生成的 token 统计对象

        Args:
            messages: 消息列表（用于计算 prompt_tokens）
            reasoning: 推理内容（用于计算 reasoning_tokens）
            content: 回答内容（用于计算 content_tokens）

        Returns:
            ResponseGenerationTokenStats: token 统计对象
        """
        # 计算输入 token
        prompt_tokens = self.token_calculator.count_messages_tokens(input_messages)

        # 计算输出 token
        reasoning_tokens = self.token_calculator.count_tokens(reasoning)
        content_tokens = self.token_calculator.count_tokens(content)
        completion_tokens = reasoning_tokens + content_tokens

        return ResponseGenerationTokenStats(
            agent_name="response_generation",
            model_name=self.model_name,
            think_mode=self.think_mode,
            model_limit=self.token_calculator.get_max_context_tokens(),
            token_usage=self._create_token_usage(prompt_tokens, completion_tokens),
            reasoning_tokens=reasoning_tokens,
            content_tokens=content_tokens,
        )
