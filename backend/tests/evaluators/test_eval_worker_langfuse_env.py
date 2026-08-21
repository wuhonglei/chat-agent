"""eval_worker Langfuse 环境隔离。"""

from __future__ import annotations

import os

import pytest

from eval_worker import (
    LANGFUSE_ENVIRONMENT,
    OTEL_SERVICE_NAME,
    apply_eval_langfuse_env,
)


def test_apply_eval_langfuse_env_sets_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGFUSE__ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

    apply_eval_langfuse_env()

    assert os.environ["LANGFUSE__ENVIRONMENT"] == LANGFUSE_ENVIRONMENT
    assert os.environ["OTEL_SERVICE_NAME"] == OTEL_SERVICE_NAME


def test_apply_eval_langfuse_env_does_not_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE__ENVIRONMENT", "prod")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "chat-agent-backend")

    apply_eval_langfuse_env()

    assert os.environ["LANGFUSE__ENVIRONMENT"] == "prod"
    assert os.environ["OTEL_SERVICE_NAME"] == "chat-agent-backend"
