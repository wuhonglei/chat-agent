"""ModelResolver 单元测试（不依赖全局 Settings / Nacos）。"""

from __future__ import annotations

import pytest

from app.schemas.config import ModelsConfig
from app.services.base_service.model_resolver import (
    ModelResolverError,
    list_text_generation_models,
    resolve_model_ref,
    resolve_scenario,
)
from tests.test.config import MODELS_CONFIG


def _models() -> ModelsConfig:
    return ModelsConfig.model_validate(MODELS_CONFIG)


def test_resolve_model_ref_builds_llm_config() -> None:
    cfg = resolve_model_ref("qwen/qwen3.7-plus", _models())

    assert cfg.model_name == "qwen3.7-plus"
    assert cfg.api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert cfg.api_key == "sk-test-qwen"
    assert cfg.context_limit == 128000
    assert cfg.title == "Qwen3.7 Plus"
    # capabilities 含 image -> image_support True
    assert cfg.image_support is True


def test_resolve_model_ref_text_only_model_has_no_image_support() -> None:
    cfg = resolve_model_ref("deepseek/deepseek-v4-flash", _models())
    assert cfg.image_support is False


def test_resolve_scenario_uses_default_model() -> None:
    cfg = resolve_scenario("title_generation", _models())
    assert cfg.model_name == "qwen3.7-max"


def test_list_text_generation_models_dedupes_and_preserves_order() -> None:
    items = list_text_generation_models(_models())
    refs = [ref for ref, _ in items]

    assert refs[0] == "qwen/qwen3.7-plus"  # default_model first
    assert refs == list(dict.fromkeys(refs))  # no duplicates
    assert "kimi/kimi-k2.6" in refs


def test_resolve_model_ref_rejects_invalid_format() -> None:
    with pytest.raises(ModelResolverError):
        resolve_model_ref("not-a-valid-ref", _models())


def test_resolve_model_ref_unknown_provider() -> None:
    with pytest.raises(ModelResolverError):
        resolve_model_ref("unknown/whatever", _models())


def test_resolve_model_ref_unknown_model() -> None:
    with pytest.raises(ModelResolverError):
        resolve_model_ref("qwen/does-not-exist", _models())


def test_resolve_scenario_unknown_scenario() -> None:
    with pytest.raises(ModelResolverError):
        resolve_scenario("nonexistent", _models())


def test_provider_model_requires_context_limit() -> None:
    invalid = {
        "providers": {
            "qwen": {
                "base_url": "https://example.com/v1",
                "api_key": "sk-test",
                "models": {
                    # 缺少 context_limit -> 校验失败
                    "qwen3.7-plus": {"name": "Qwen3.7 Plus", "capabilities": ["text"]}
                },
            }
        },
        "scenarios": {
            "text_generation": {"default_model": "qwen/qwen3.7-plus"},
            "title_generation": {"default_model": "qwen/qwen3.7-plus"},
            "summarization": {"default_model": "qwen/qwen3.7-plus"},
        },
    }
    with pytest.raises(ValueError):
        ModelsConfig.model_validate(invalid)
