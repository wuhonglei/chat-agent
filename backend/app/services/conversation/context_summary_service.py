"""上下文摘要服务：窗口外消息摘要"""

from __future__ import annotations

from app.core.config import settings
from app.prompts.prompt_utils import (
    get_window_out_summary_merge_prompt,
)
from app.schemas.chat import (
    ChatMessage,
    collect_text_from_blocks,
)
from app.schemas.config import LLMConfig
from app.services.base_service.llm_service import LLMService
from app.utils.logger import logger


class ContextSummaryService(LLMService):
    """窗口外消息摘要（调用 LLM，继承 LLMService 统一 API 调用）"""

    def __init__(self) -> None:
        cfg = settings.summarizer_model
        llm_config = LLMConfig(
            api_key=cfg.api_key,
            api_base=cfg.api_base,
            model_name=cfg.model_name,
            think_model_name=cfg.model_name,
        )
        super().__init__(llm_config, think_mode=False)

    def format_conversation_for_summary(
        self,
        messages: list[ChatMessage],
    ) -> str:
        """将消息列表拼接为一段文本供 LLM 阅读"""
        parts: list[str] = []
        for m in messages:
            role = m.role
            text_content = collect_text_from_blocks(m.content_blocks, only_last=True)
            if text_content.strip():
                parts.append(f"[{role}]: {text_content.strip()}")
        return "\n\n".join(parts)

    async def summarize_merge(
        self,
        prior_summary: str | None,
        messages_to_summarize: list[ChatMessage],
        max_tokens: int,
    ) -> str:
        """生成或增量合并窗口外摘要。"""
        normalized_prior_summary = prior_summary.strip() if prior_summary else ""
        if not messages_to_summarize:
            return normalized_prior_summary[: max_tokens * 2]
        new_text = self.format_conversation_for_summary(messages_to_summarize)
        if not new_text.strip():
            return normalized_prior_summary[: max_tokens * 2]

        max_source_tokens = int(
            self.model_limit * (0.8 if normalized_prior_summary else 0.5)
        )
        new_truncated = self.token_calculator.truncate_text_to_tokens(
            new_text, max_tokens=max_source_tokens
        )
        prompt = get_window_out_summary_merge_prompt(
            prior_summary=normalized_prior_summary,
            new_messages_text=new_truncated,
            max_tokens=max_tokens,
        )
        try:
            resp = await self.call_llm_api(
                self.model_name,
                [{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=max_tokens,
                extra_body=self.extra_body,
            )
            content = (resp.choices[0].message.content or "").strip()
            return content[: max_tokens * 2]
        except Exception as e:
            logger.warning(
                "Window-out merge summary LLM call failed",
                error=e,
                message_count=len(messages_to_summarize),
            )
            return normalized_prior_summary[: max_tokens * 2]
