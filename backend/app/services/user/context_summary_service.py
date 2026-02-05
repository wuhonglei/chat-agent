"""上下文摘要服务：窗口外消息摘要与用户事实/偏好归纳"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.prompts.prompt_utils import get_window_out_summary_prompt
from app.prompts.user_prompt import USER_FACTS_PREFERENCES_PROMPT
from app.schemas.chat import ChatMessageItem
from app.utils.logger import logger
from app.utils.token import TokenCalculator


class ContextSummaryService:
    """窗口外摘要与用户事实/偏好归纳（调用 LLM）"""

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

    async def extract_user_facts_preferences(
        self,
        text: str,
        existing_facts: list[str] | None = None,
        existing_preferences: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """从对话文本中归纳用户事实与偏好，可与已有记录合并"""
        if not text or not text.strip():
            return (existing_facts or []), (existing_preferences or [])
        existing_facts = existing_facts or []
        existing_preferences = existing_preferences or []
        prompt = USER_FACTS_PREFERENCES_PROMPT.render(
            existing_facts=existing_facts,
            existing_preferences=existing_preferences,
            text=text[:6000],
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )
            raw = (resp.choices[0].message.content or "").strip()
            # 简单解析 JSON（可能被 markdown 包裹）
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            facts = list(data.get("facts") or [])
            preferences = list(data.get("preferences") or [])
            # 与已有合并去重
            all_facts = list(dict.fromkeys(existing_facts + facts))
            all_prefs = list(dict.fromkeys(existing_preferences + preferences))
            return (all_facts, all_prefs)
        except Exception as e:
            logger.warning(
                "Extract user facts/preferences LLM call failed",
                error=e,
            )
            return (existing_facts, existing_preferences)
