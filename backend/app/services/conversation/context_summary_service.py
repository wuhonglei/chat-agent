"""上下文摘要服务：窗口外消息摘要"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings
from app.prompts.prompt_utils import (
    get_window_out_summary_merge_prompt,
    get_window_out_summary_prompt,
)
from app.schemas.chat import ChatMessageItem
from app.utils.logger import logger
from app.utils.token import TokenCalculator


class ContextSummaryService:
    """窗口外消息摘要（调用 LLM）"""

    def __init__(self) -> None:
        cfg = settings.summarizer_model
        self._client = AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.api_base,
        )
        self._model = cfg.model_name
        self._token_calculator = TokenCalculator(cfg.model_name)

    def _messages_to_text(self, messages: list[ChatMessageItem]) -> str:
        """将消息列表拼接为一段文本供 LLM 阅读"""
        parts: list[str] = []
        for m in messages:
            role = getattr(m, "role", "unknown")
            content = getattr(m, "content", "") or ""
            if content.strip():
                parts.append(f"[{role}]: {content.strip()}")
        return "\n\n".join(parts)

    async def summarize_truncated_messages(
        self,
        truncated_messages: list[ChatMessageItem],
        max_tokens: int,
    ) -> str:
        """对截断的旧消息生成简短摘要"""
        if not truncated_messages:
            return ""
        text = self._messages_to_text(truncated_messages)
        if not text.strip():
            return ""
        truncated_text = self._token_calculator.truncate_text_to_tokens(
            text, max_tokens=8000
        )
        prompt = get_window_out_summary_prompt(
            text=truncated_text, max_tokens=max_tokens
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            return content[: max_tokens * 2]  # 粗略防止超长
        except Exception as e:
            logger.warning(
                "Window-out summary LLM call failed",
                error=e,
                message_count=len(truncated_messages),
            )
            return ""

    async def summarize_merge(
        self,
        prior_summary: str,
        new_messages: list[ChatMessageItem],
        max_tokens: int,
    ) -> str:
        """将已有摘要与新增消息内容合并为一段简短摘要（增量摘要）。"""
        if not prior_summary.strip():
            return await self.summarize_truncated_messages(
                new_messages, max_tokens=max_tokens
            )
        new_text = self._messages_to_text(new_messages)
        if not new_text.strip():
            return prior_summary.strip()[: max_tokens * 2]
        prior_truncated = self._token_calculator.truncate_text_to_tokens(
            prior_summary, max_tokens=4000
        )
        new_truncated = self._token_calculator.truncate_text_to_tokens(
            new_text, max_tokens=4000
        )
        prompt = get_window_out_summary_merge_prompt(
            prior_summary=prior_truncated,
            new_messages_text=new_truncated,
            max_tokens=max_tokens,
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            return content[: max_tokens * 2]
        except Exception as e:
            logger.warning(
                "Window-out merge summary LLM call failed",
                error=e,
                new_message_count=len(new_messages),
            )
            return prior_summary.strip()[: max_tokens * 2]
