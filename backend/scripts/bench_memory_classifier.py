"""单独验证 memory 分类小模型调用耗时（不依赖后端服务，直接调 LLMService）。

用法: uv run python scripts/bench_memory_classifier.py [ref ...]
默认对比 dashscope/qwen3.7-flash 与 deepseek/deepseek-v4-flash。
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time

from app.schemas.config import LLMConfig
from app.services.base_service.llm_service import LLMService
from app.services.base_service.model_resolver import resolve_model_ref

CLASSIFIER_PROMPT = """Classify whether this user message needs personal memory context to answer well.

YES: The answer would be better with knowledge of this user's preferences, history, past decisions, or personal context.
NO: The question can be answered well without any personal context (general knowledge, code help, translation, math, etc.)

User message: "{query}"

Respond with ONLY YES or NO."""

QUERIES = [
    "我之前定的技术栈是什么？",  # NEEDS
    "帮我写一个快速排序",  # NO
    "我上次为什么决定不用 LangChain？",  # NEEDS
    "深圳明天天气怎么样",  # NO
    "根据我的偏好帮我review这段代码",  # NEEDS
    "翻译这段英文：Hello world",  # NO
    "我之前的项目里是怎么做记忆的？",  # NEEDS
    "什么是 OAuth2.0",  # NO
]

WARMUP = 1
ROUNDS = 5


# deepseek-v4-flash 默认带 reasoning；禁用后才能用小 max_tokens 拿到稳定单词输出
MAX_TOKENS = {"deepseek": 64}
DEFAULT_MAX_TOKENS = 5
NO_THINK_EXTRA_BODY = {"enable_thinking": False, "thinking": {"type": "disabled"}}


async def bench(ref: str) -> None:
    try:
        cfg = resolve_model_ref(ref)
    except Exception:
        # 未在 models.providers 注册的模型：借用同名 provider 的凭证临时构造
        provider_name, _, model_key = ref.partition("/")
        from app.core.config import settings

        provider = settings.models.providers[provider_name]
        cfg = LLMConfig(
            api_key=provider.api_key,
            api_base=provider.base_url,
            model_name=model_key,
            context_limit=1_000_000,
            max_output_tokens=8_192,
            title=model_key,
            description="bench ad-hoc",
        )
    svc = LLMService(cfg)
    max_tokens = DEFAULT_MAX_TOKENS  # 禁用思考后统一用 5
    extra_body = (
        NO_THINK_EXTRA_BODY if ref.split("/")[0] in ("deepseek", "dashscope") else None
    )

    async def one(query: str) -> tuple[bool, str, float]:
        t0 = time.perf_counter()
        resp = await svc.client.chat.completions.create(
            model=cfg.model_name,
            messages=[
                {"role": "user", "content": CLASSIFIER_PROMPT.format(query=query)}
            ],
            max_tokens=max_tokens,
            temperature=0.0,
            extra_body=extra_body,
        )
        dt = time.perf_counter() - t0
        content = (resp.choices[0].message.content or "").strip()
        return content.upper().startswith("YES"), content, dt

    # warmup（建连 + 首次 TLS）
    await svc.client.chat.completions.create(
        model=cfg.model_name,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
    )

    records = []
    total_wall = 0.0
    round_start = time.perf_counter()
    for r in range(ROUNDS):
        round_start = time.perf_counter()
        for q in QUERIES:
            ok, content, dt = await one(q)
            records.append(
                {
                    "round": r,
                    "query": q,
                    "pred": ok,
                    "raw": content,
                    "latency_ms": round(dt * 1000, 1),
                }
            )
        total_wall += time.perf_counter() - round_start

    lats = [x["latency_ms"] for x in records]
    print(f"\n===== {ref} ({ROUNDS} rounds x {len(QUERIES)} queries, 串行) =====")
    print(
        f"latency ms: min={min(lats):.0f} p50={statistics.median(lats):.0f} "
        f"mean={statistics.mean(lats):.0f} max={max(lats):.0f} stdev={statistics.pstdev(lats):.0f}"
    )
    bad = [x for x in records if x["raw"].upper().strip() not in ("YES", "NO")]
    if bad:
        print("!! 非法输出:", json.dumps(bad, ensure_ascii=False))
    for x in records:
        if x["round"] == 0:
            print(
                f"  round0 [{x['latency_ms']:7.1f}ms] {'NEEDS ' if x['pred'] else 'NO    '} {x['raw']!r} <- {x['query']}"
            )


async def main() -> None:
    refs = sys.argv[1:] or ["dashscope/qwen3.8-flash"]
    for ref in refs:
        await bench(ref)


if __name__ == "__main__":
    asyncio.run(main())
