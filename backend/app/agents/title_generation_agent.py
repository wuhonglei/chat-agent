"""Title Generation Agent for generating conversation titles"""
from typing import Any, Optional

from app.schemas.config import LLMConfig
from app.schemas.token_stats import TitleGenerationTokenStats
from app.utils.time import get_current_time, get_time_duration
from app.prompts import get_prompt_for_title
from app.agents.base import BaseAgent


class TitleGenerationAgent(BaseAgent):
    """标题生成Agent - 负责生成对话标题"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig):
        super().__init__(think_mode, llm_config)
        self.duration: Optional[float] = None
        self.token_stats: Optional[TitleGenerationTokenStats] = None

    def create_token_stats(
        self,
        messages: list[dict],
        title: str,
    ) -> TitleGenerationTokenStats:
        """创建标题生成的 token 统计对象

        Args:
            messages: 消息列表（用于计算 prompt_tokens）
            title: 生成的标题（用于计算 completion_tokens）

        Returns:
            TitleGenerationTokenStats: token 统计对象
        """
        # 计算输入 token
        prompt_tokens = self.token_calculator.count_messages_tokens(messages)

        # 计算输出 token
        completion_tokens = self.token_calculator.count_tokens(title)

        return TitleGenerationTokenStats(
            agent_name="title_generation",
            model_name=self.model_name,
            think_mode=self.think_mode,
            model_limit=self.model_limit,
            token_usage=self._create_token_usage(
                prompt_tokens, completion_tokens),
            title=title
        )

    async def execute(self, user_message: str) -> str:
        """
        生成对话标题

        Args:
            user_message: 用户消息

        Returns:
            str: 生成的标题
        """
        start_time = get_current_time()
        system_prompt, new_user_message = get_prompt_for_title(user_message)
        messages = self._compose_messages(system_prompt, [], new_user_message)

        title_response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=False,
        )

        self.duration = get_time_duration(start_time)
        title = title_response.choices[0].message.content or ""

        # 创建 token 统计对象（内部进行所有 token 计算）
        self.token_stats = self.create_token_stats(
            messages=messages,
            title=title
        )

        return title
