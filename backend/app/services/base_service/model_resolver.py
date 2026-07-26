"""模型解析：将 provider/model 引用解析为运行时 LLMConfig。

配置结构见 app.schemas.config.ModelsConfig（providers + scenarios 两层）。
引用格式统一为 "provider_name/model_name"，例如 "dashscope/kimi-k2.6"。
"""

from __future__ import annotations

from app.schemas.config import (
    LLMConfig,
    ModelsConfig,
    ProviderConfig,
    ProviderModelMeta,
)


class ModelResolverError(ValueError):
    """模型引用无法解析（格式非法、provider/model 不存在等）。"""


def infer_max_output_tokens(context_limit: int) -> int:
    """按上下文窗口档位推测默认输出预留（对齐常见模型能力）。"""
    if context_limit <= 4_096:
        return max(512, context_limit // 4)
    if context_limit <= 8_192:
        return max(1_024, context_limit // 4)
    if context_limit <= 16_384:
        return 4_096
    if context_limit <= 32_768:
        return 4_096
    if context_limit <= 65_536:
        return 8_192
    if context_limit <= 131_072:
        return 8_192
    if context_limit <= 262_144:
        return 16_384
    if context_limit <= 524_288:
        return 32_768
    if context_limit <= 1_048_576:
        return 32_768
    return 65_536


def _resolve_models(models: ModelsConfig | None) -> ModelsConfig:
    if models is not None:
        return models
    # 延迟导入：避免在仅传入显式 ModelsConfig 时触发全局 Settings 构建。
    from app.core.config import settings

    return settings.models


def _split_ref(ref: str) -> tuple[str, str]:
    provider_name, _, model_key = ref.partition("/")
    if not provider_name or not model_key:
        raise ModelResolverError(f"非法模型引用: {ref!r}，应为 'provider/model_name'")
    return provider_name, model_key


def _build_llm_config(
    provider: ProviderConfig, model_key: str, meta: ProviderModelMeta
) -> LLMConfig:
    max_output_tokens = (
        meta.max_output_tokens
        if meta.max_output_tokens is not None
        else infer_max_output_tokens(meta.context_limit)
    )
    return LLMConfig(
        api_key=provider.api_key,
        api_base=provider.base_url,
        model_name=model_key,
        context_limit=meta.context_limit,
        max_output_tokens=max_output_tokens,
        title=meta.name,
        description=meta.description,
        image_support="image" in meta.capabilities,
    )


def resolve_model_ref(ref: str, models: ModelsConfig | None = None) -> LLMConfig:
    """将 'provider/model_name' 引用解析为运行时 LLMConfig。"""
    cfg = _resolve_models(models)
    provider_name, model_key = _split_ref(ref)

    provider = cfg.providers.get(provider_name)
    if provider is None:
        raise ModelResolverError(f"未找到 provider: {provider_name!r}（ref={ref!r}）")

    meta = provider.models.get(model_key)
    if meta is None:
        raise ModelResolverError(
            f"provider {provider_name!r} 下未找到模型: {model_key!r}（ref={ref!r}）"
        )

    return _build_llm_config(provider, model_key, meta)


def resolve_scenario(name: str, models: ModelsConfig | None = None) -> LLMConfig:
    """读取场景的 default_model 并解析为 LLMConfig。"""
    cfg = _resolve_models(models)
    scenario = cfg.scenarios.get(name)
    if scenario is None:
        raise ModelResolverError(f"未找到场景: {name!r}")
    return resolve_model_ref(scenario.default_model, cfg)


def list_text_generation_models(
    models: ModelsConfig | None = None,
) -> list[tuple[str, LLMConfig]]:
    """返回对话可选模型列表（default_model + alternatives，按序去重）。"""
    cfg = _resolve_models(models)
    scenario = cfg.scenarios.get("text_generation")
    if scenario is None:
        raise ModelResolverError("未找到场景: 'text_generation'")

    seen: set[str] = set()
    result: list[tuple[str, LLMConfig]] = []
    for ref in [scenario.default_model, *scenario.alternatives]:
        if ref in seen:
            continue
        seen.add(ref)
        result.append((ref, resolve_model_ref(ref, cfg)))
    return result
