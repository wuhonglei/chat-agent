"""独立记忆治理 Worker 进程包。

按用户 fan-out 触发 Mem0 OSS 的 ``POST /dream``（见 ``backend/docs/MEMORY_GOVERNANCE_WORKER.md``）。
与 ``eval_worker`` 同镜像、不同 command，互不影响。
"""

from __future__ import annotations

import os

LANGFUSE_ENVIRONMENT = "memory_worker"
OTEL_SERVICE_NAME = "chat-agent-memory-governance"


def apply_worker_env() -> None:
    """在加载 Settings / init_langfuse 之前设置本 Worker 的 Langfuse 环境。

    必须在 ``app.core.config`` 首次构造 Settings 之前调用，这样
    ``LANGFUSE__ENVIRONMENT`` 才能覆盖 Nacos 里的 prod/dev。
    """
    os.environ.setdefault("LANGFUSE__ENVIRONMENT", LANGFUSE_ENVIRONMENT)
    os.environ.setdefault("OTEL_SERVICE_NAME", OTEL_SERVICE_NAME)


apply_worker_env()
