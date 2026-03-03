"""Skill 基类定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillContext:
    """Skill 执行上下文"""

    user_id: str | None = None
    session_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 执行结果"""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseSkill(ABC):
    """Skill 基类"""

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        context: SkillContext | None = None,
    ) -> SkillResult:
        """执行 Skill"""
        pass
