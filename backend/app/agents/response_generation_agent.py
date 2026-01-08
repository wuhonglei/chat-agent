"""Response Generation Agent for generating final chat responses"""
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.chat import ChatMessageItemReq
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolCallMessage
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.utils.model import get_model_extra_body
from app.prompts import get_default_system_prompt
from app.agents.base import BaseAgent


class ResponseGenerationAgent(BaseAgent):
    """响应生成Agent - 负责生成最终的聊天响应"""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        self.content = ''
        self.reasoning = ''
        self.reasoning_duration: Optional[float] = None
        self.content_duration: Optional[float] = None
        self.total_duration: Optional[float] = None

    def format_sse_message(self, msg_type: str, data=None) -> str:
        """格式化SSE消息，并更新状态（如果需要）"""
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="json")
        if msg_type == 'content':
            self.content += data.get('content') or ''
        elif msg_type == 'reasoning':
            self.reasoning += data.get('content') or ''

        return super().format_sse_message(msg_type, data)

    async def stream_execute(
        self,
        history: list[ChatMessageItemReq],
        user_message: str,
        mcp_tool_call_messages: list[ToolCallMessage],
        component_tool_call_messages: list[ToolCallMessage],
        think_mode: bool,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成最终响应

        Args:
            history: 对话历史
            user_message: 用户消息（已包含组件数据）
            mcp_tool_call_messages: MCP工具调用消息
            component_tool_call_messages: 组件工具调用消息
            think_mode: 是否使用思考模式

        Yields:
            str: SSE格式的响应消息
        """
        system_prompt = get_default_system_prompt(include_date=False)
        new_messages = self._compose_messages(
            system_prompt, history, user_message, mcp_tool_call_messages)
        final_model = self.model_config.think_model if think_mode else self.model_config.model
        extra_body = get_model_extra_body(think_mode)
        async for chunk in self._stream_final_response(new_messages, final_model, extra_body):
            yield chunk

    async def _stream_final_response(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream final response"""
        start_time = get_current_time()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            extra_body=extra_body,
        )
        logger.info("Using LLM model", model=model)
        reasoning_started = False
        content_started = False
        # 重命名变量，区分推理和内容的计时，避免混淆
        last_reasoning_time = start_time
        last_content_time = start_time

        async for chunk in response:
            # 安全检查：确保 choices 存在且不为空
            if not chunk.choices:
                continue

            delta = getattr(chunk.choices[0], 'delta', None)
            if not delta:
                continue

            # 处理 reasoning_content
            reasoning_content = getattr(delta, 'reasoning_content', None)
            content = getattr(delta, 'content', None)

            # 1. 优先处理推理内容（允许同时存在推理和内容的极端情况）
            if reasoning_content:
                # 如果之前在输出 content，先结束 content
                if content_started:
                    content_duration = get_time_duration(last_content_time)
                    self.content_duration = content_duration
                    yield self.format_sse_message('content', {
                        'status': 'done',
                        'content': '',
                        'duration': content_duration,
                    })
                    content_started = False

                status = 'start' if not reasoning_started else 'continue'
                reasoning_started = True
                last_reasoning_time = get_current_time()
                yield self.format_sse_message('reasoning', {
                    'status': status,
                    'content': reasoning_content,
                })

            # 2. 处理 content（不再用 elif，避免推理内容覆盖内容的判断）
            if content:
                # 如果之前在输出 reasoning，先结束 reasoning
                if reasoning_started:
                    reasoning_duration = get_time_duration(last_reasoning_time)
                    self.reasoning_duration = reasoning_duration
                    yield self.format_sse_message('reasoning', {
                        'status': 'done',
                        'duration': reasoning_duration,
                    })
                    reasoning_started = False

                status = 'start' if not content_started else 'continue'
                content_started = True
                last_content_time = get_current_time()
                yield self.format_sse_message('content', {
                    'status': status,
                    'content': content,
                })

        # 处理循环结束后的收尾逻辑（关键修复：分开判断，不再用 elif）
        # 1. 如果推理未结束，发送推理 done 状态
        if reasoning_started:
            reasoning_duration = get_time_duration(last_reasoning_time)
            self.reasoning_duration = reasoning_duration
            yield self.format_sse_message('reasoning', {
                'status': 'done',
                'duration': reasoning_duration,
            })

        # 2. 如果内容未结束，发送内容 done 状态（独立判断，即使有推理也会处理）
        if content_started:
            content_duration = get_time_duration(last_content_time)
            self.content_duration = content_duration
            yield self.format_sse_message('content', {
                'status': 'done',
                'content': '',
                'duration': content_duration,
            })

        # 3. 关键补充：处理「有推理但无内容」的边界情况
        if reasoning_started and not content_started and not content:
            # 发送一个空的 content done 状态，确保前端感知到内容结束
            yield self.format_sse_message('content', {
                'status': 'done',
                'content': '[模型已完成深入推理，详见思考过程]',
                'duration': 0.0,
            })

        logger.info("Stream final response completed",
                    duration=self.total_duration)
        self.total_duration = get_time_duration(start_time)
