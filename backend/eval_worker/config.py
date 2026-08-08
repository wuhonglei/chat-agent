"""评估 Worker 配置读取。"""

from __future__ import annotations

from app.core.config import settings
from app.schemas.config import EvalWorkerConfig


def get_eval_worker_config() -> EvalWorkerConfig:
    return settings.eval_worker
