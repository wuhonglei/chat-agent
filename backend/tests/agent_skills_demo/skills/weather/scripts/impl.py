"""Weather Skill 实现（模拟数据）"""

import random
from pathlib import Path
from typing import Any

from ...base import BaseSkill, SkillContext, SkillResult

# 模拟天气状况
_CONDITIONS = ["晴", "多云", "阴", "小雨", "雷阵雨", "雾", "霾"]


class SkillImpl(BaseSkill):
    """天气查询 Skill 实现（模拟）"""

    async def execute(
        self,
        params: dict[str, Any],
        context: SkillContext | None = None,
    ) -> SkillResult:
        city = params.get("city", "")
        if not city or not isinstance(city, str):
            return SkillResult(success=False, error="缺少 city 参数")

        # 使用城市名作为种子，保证同一城市返回一致结果（演示用）
        seed = hash(city.strip()) % (2**32)
        rng = random.Random(seed)

        # schemas 在 skill 根目录，impl 在 scripts/ 下，需向上一级
        schema_path = Path(__file__).parent.parent / "schemas" / "response.json"
        data = {
            "city": city.strip(),
            "temperature": round(rng.uniform(-5, 35), 1),
            "condition": rng.choice(_CONDITIONS),
            "humidity": rng.randint(30, 95),
            "wind_speed": round(rng.uniform(0, 30), 1),
        }

        return SkillResult(
            success=True,
            data=data,
            metadata={"schema_path": str(schema_path)},
        )
