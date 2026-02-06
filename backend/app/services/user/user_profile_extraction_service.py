"""用户画像归纳服务：从对话文本中归纳用户事实与偏好（调用 LLM）"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings
from app.prompts.user_prompt import USER_FACTS_PREFERENCES_PROMPT
from app.utils.common import parse_json_from_text
from app.utils.logger import logger


class UserProfileExtractionService:
    """从文本中归纳用户事实与偏好，供后续写入 user_profile_items。"""

    def __init__(self) -> None:
        cfg = settings.summarizer_model
        self._client = AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.api_base,
        )
        self._model = cfg.model_name

    async def extract_user_facts_preferences(
        self,
        text: str,
        existing_facts: list[str] | None = None,
        existing_preferences: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """从对话文本中归纳用户事实与偏好，可与已有记录合并。"""
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
            data = parse_json_from_text(raw)
            all_facts = list(
                dict.fromkeys(existing_facts + list(data.get("facts") or []))
            )
            all_prefs = list(
                dict.fromkeys(
                    existing_preferences + list(data.get("preferences") or [])
                )
            )
            return (all_facts, all_prefs)
        except Exception as e:
            logger.warning(
                "Extract user facts/preferences LLM call failed",
                error=e,
            )
            return (existing_facts, existing_preferences)
