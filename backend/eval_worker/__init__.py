"""独立评估 Worker 进程包。"""

from __future__ import annotations

import os

LANGFUSE_ENVIRONMENT = "eval_worker"
OTEL_SERVICE_NAME = "chat-agent-eval-worker"


def apply_eval_langfuse_env() -> None:
    """在加载 Settings / init_langfuse 之前设置评估专用 Langfuse 环境。

    必须在 ``app.core.config`` 首次构造 Settings 之前调用，这样
    ``LANGFUSE__ENVIRONMENT`` 才能覆盖 Nacos 里的 prod/dev。
    """
    os.environ.setdefault("LANGFUSE__ENVIRONMENT", LANGFUSE_ENVIRONMENT)
    os.environ.setdefault("OTEL_SERVICE_NAME", OTEL_SERVICE_NAME)


apply_eval_langfuse_env()
