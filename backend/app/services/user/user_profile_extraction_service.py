"""用户画像归纳服务：从对话文本中归纳用户事实与偏好（调用 LLM）"""

from __future__ import annotations

from app.core.config import settings
from app.prompts import get_user_facts_preferences_prompt
from app.schemas.config import LLMConfig
from app.services.base_service.llm_service import LLMService
from app.utils.common import parse_json_from_text
from app.utils.logger import logger


class UserProfileExtractionService(LLMService):
    """从文本中归纳用户事实与偏好，供后续写入 user_profile_items。"""

    def __init__(self) -> None:
        cfg = settings.summarizer_model
        llm_config = LLMConfig(
            api_key=cfg.api_key,
            api_base=cfg.api_base,
            model_name=cfg.model_name,
            think_model_name=cfg.model_name,
        )
        super().__init__(llm_config, think_mode=False)

    async def extract_user_facts_preferences(
        self,
        user_message_content: str,
        assistant_content: str,
        summary: str | None = None,
        existing_facts: list[str] | None = None,
        existing_preferences: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """从对话文本中归纳用户事实与偏好，可与已有记录合并。"""
        existing_facts = existing_facts or []
        existing_preferences = existing_preferences or []
        prompt = get_user_facts_preferences_prompt(
            user_message_content=user_message_content,
            assistant_content=assistant_content,
            existing_facts=existing_facts,
            existing_preferences=existing_preferences,
            summary=summary,
        )
        try:
            resp = await self.call_llm_api(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=settings.compression.user_profile_extraction_max_tokens,
            )
            raw = (resp.choices[0].message.content or "").strip()
            data = parse_json_from_text(raw)
            new_facts_raw = list(data.get("facts") or [])
            new_prefs_raw = list(data.get("preferences") or [])
            if not new_facts_raw and not new_prefs_raw:
                return ([], [])

            new_facts = [
                f for f in dict.fromkeys(new_facts_raw) if f not in existing_facts
            ]
            new_prefs = [
                p for p in dict.fromkeys(new_prefs_raw) if p not in existing_preferences
            ]
            return (new_facts, new_prefs)
        except Exception as e:
            logger.warning(
                "Extract user facts/preferences LLM call failed",
                error=e,
            )
            return ([], [])
