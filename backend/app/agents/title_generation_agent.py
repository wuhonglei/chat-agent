"""Title Generation Agent for generating conversation titles"""
from typing import Optional

from app.schemas.config import LLMConfig
from app.utils.time import get_current_time, get_time_duration
from app.prompts import get_prompt_for_title
from app.agents.base import BaseAgent


class TitleGenerationAgent(BaseAgent):
    """标题生成Agent - 负责生成对话标题"""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        self.duration: Optional[float] = None

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
            model=self.model_config.model,
            messages=messages,
            stream=False,
        )
        self.duration = get_time_duration(start_time)
        return title_response.choices[0].message.content
