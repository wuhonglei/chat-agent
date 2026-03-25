"""Title Generation Agent for generating conversation titles"""

from typing import Any

from app.agents.base import BaseAgent
from app.prompts.prompt_utils import get_system_prompt_for_title
from app.schemas.config import LLMConfig
from app.schemas.content import ContentPart
from app.schemas.token_stats import TitleGenerationTokenStats
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


class TitleGenerationAgent(BaseAgent):
    """标题生成Agent - 负责生成对话标题"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig):
        super().__init__(think_mode, llm_config)
        self.duration: float | None = None
        self.token_stats: TitleGenerationTokenStats | None = None

    def _normalize_title(self, title: str) -> str:
        max_title_length = 50

        if len(title) > max_title_length:
            original_title = title
            truncated_title = title[:max_title_length]
            logger.warning(
                "Title truncated due to excessive length",
                original_length=len(original_title),
                max_length=max_title_length,
                original_title=original_title,
                truncated_title=truncated_title,
            )
            title = truncated_title

        if "\n" in title:
            original_title = title
            truncated_title = title.split("\n")[0]
            logger.warning(
                "Title truncated due to newline",
                original_title=original_title,
                truncated_title=truncated_title,
            )
            title = truncated_title

        return title

    def create_token_stats(  # type: ignore[override]
        self,
        messages: list[dict[str, Any]],
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
            token_usage=self._create_token_usage(prompt_tokens, completion_tokens),
            title=title,
        )

    async def execute(self, user_message: str | list[ContentPart]) -> str:
        """
        生成对话标题

        Args:
            user_message: 用户消息

        Returns:
            str: 生成的标题
        """
        start_time = get_current_time()
        system_prompt = get_system_prompt_for_title()
        messages = self._compose_messages(system_prompt, [], user_message)

        title_response = await self.call_llm_api(
            model=self.model_name,
            messages=messages,
            stream=False,
        )

        self.duration = get_time_duration(start_time)
        title = title_response.choices[0].message.content or ""
        title = self._normalize_title(title)

        # 创建 token 统计对象（内部进行所有 token 计算）
        self.token_stats = self.create_token_stats(messages=messages, title=title)

        return title
