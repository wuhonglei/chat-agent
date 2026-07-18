"""Settings reload must invalidate model configuration cached in L1."""

from __future__ import annotations

from unittest.mock import patch

from app.core import config
from app.core.local_cache import l1_get, l1_set


def test_reload_settings_clears_models_cache() -> None:
    l1_set("models", "global", ["cached-model"])
    assert l1_get("models", "global") == ["cached-model"]

    with (
        patch.object(config, "_build_settings", return_value=config._current_settings),
        patch("app.mcp.reload.on_settings_reloaded"),
    ):
        config.reload_settings()

    assert l1_get("models", "global") is None
