"""Title Generation Agent for generating conversation titles"""
from typing import Any, Optional

from app.schemas.config import LLMConfig
from app.schemas.token_stats import TitleGenerationTokenStats
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator
from app.prompts import get_prompt_for_title
from app.agents.base import BaseAgent


class TitleGenerationAgent(BaseAgent):
    """标题生成Agent - 负责生成对话标题"""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        self.duration: Optional[float] = None
        self.token_stats: Optional[TitleGenerationTokenStats] = None

    def _create_token_stats(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
        duration: Optional[float],
        **kwargs: Any
    ) -> TitleGenerationTokenStats:
        """创建标题生成的 token 统计对象"""
        return TitleGenerationTokenStats(
            agent_name="title_generation_agent",
            model_name=model_name,
            token_usage=self._create_token_usage(
                prompt_tokens, completion_tokens),
            duration=duration,
            title=kwargs.get('title')
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

        # 初始化 token 统计
        token_calculator = TokenCalculator(self.model_config.model)
        prompt_tokens = token_calculator.count_messages_tokens(messages)

        title_response = await self.client.chat.completions.create(
            model=self.model_config.model,
            messages=messages,
            stream=False,
        )

        self.duration = get_time_duration(start_time)
        title = title_response.choices[0].message.content or ""

        # 计算输出 token
        completion_tokens = token_calculator.count_tokens(title)

        # 创建 token 统计对象
        self.token_stats = self._create_token_stats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_name=self.model_config.model,
            duration=self.duration,
            title=title,
        )

        return title
