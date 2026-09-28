"""启动时模型场景校验。"""

from __future__ import annotations

import copy

import pytest

from app.core.config import validate_models_config
from app.schemas.config import ModelsConfig
from tests.test.config import MODELS_CONFIG


def _models(**scenario_overrides: object) -> ModelsConfig:
    raw = copy.deepcopy(MODELS_CONFIG)
    raw["scenarios"].update(scenario_overrides)
    return ModelsConfig.model_validate(raw)


def test_missing_vision_scenario_fails() -> None:
    models = _models()
    with pytest.raises(ValueError, match="vision"):
        validate_models_config(models)


def test_vision_text_only_model_fails() -> None:
    models = _models(
        vision={"default_model": "deepseek/deepseek-v4-flash"},
    )
    with pytest.raises(ValueError, match="image"):
        validate_models_config(models)


def test_vision_text_only_alternative_fails() -> None:
    models = _models(
        vision={
            "default_model": "qwen/qwen3.7-plus",
            "alternatives": ["deepseek/deepseek-v4-flash"],
        },
    )
    with pytest.raises(ValueError, match="image"):
        validate_models_config(models)


def test_vision_image_model_passes() -> None:
    models = _models(
        vision={"default_model": "qwen/qwen3.7-plus"},
    )
    validate_models_config(models)
