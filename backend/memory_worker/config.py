"""记忆治理 Worker 配置读取。"""

from __future__ import annotations

from app.core.config import settings
from app.schemas.config import MemoryGovernanceWorkerConfig


def get_memory_governance_config() -> MemoryGovernanceWorkerConfig:
    return settings.memory_governance_worker
