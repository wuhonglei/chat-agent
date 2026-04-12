"""Title Generation Agent for generating conversation titles"""

from typing import Any

from app.agents.base import BaseAgent
from app.prompts import get_prompt_for_title
from app.schemas.chat import ContentBlock
from app.schemas.config import LLMConfig
from app.utils.logger import logger


class TitleGenerationAgent(BaseAgent):
    """标题生成Agent - 负责生成对话标题"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig):
        super().__init__(think_mode, llm_config)

    async def execute(
        self,
        user_message: str | list[ContentBlock] | list[dict[str, Any]],
    ) -> str:
        """
        生成对话标题

        Args:
            user_message: 用户消息文本，或含图片的 content_blocks

        Returns:
            str: 生成的标题
        """
        system_prompt, new_user_message = get_prompt_for_title(user_message)
        messages = self._compose_messages(system_prompt, [], new_user_message)

        title_response = await self.call_llm_api(
            model=self.model_name, messages=messages, stream=False, max_tokens=30
        )

        title = title_response.choices[0].message.content or ""
        # 防御性代码
        max_title_length = 50
        if len(title) > max_title_length:
            truncated_title = title[:max_title_length]
            logger.warning(
                "Title truncated due to excessive length",
                original_length=len(title),
                max_length=max_title_length,
                original_title=title,
                truncated_title=truncated_title,
            )
            title = truncated_title

        # 如果存在换行符，则只取第一行
        if "\n" in title:
            title = title.split("\n")[0]
            logger.warning(
                "Title truncated due to newline",
                original_title=title,
                truncated_title=title,
            )

        return title
