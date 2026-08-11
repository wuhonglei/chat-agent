"""裁判模型调用器：供批量评估 Worker / API / 脚本共用。"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.base_service.model_resolver import resolve_scenario
from app.utils.model import get_model_extra_body


async def judge_llm_caller(messages: list[dict[str, str]]) -> str:
    """裁判模型调用器。使用配置中的 judge scenario 模型。"""
    llm_config = resolve_scenario(settings.eval_worker.judge_model_scenario)
    client = AsyncOpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.api_base,
    )
    response = await client.chat.completions.create(
        model=llm_config.model_name,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.0,
        max_tokens=1024,
        extra_body=get_model_extra_body(False),
    )
    return response.choices[0].message.content or ""
