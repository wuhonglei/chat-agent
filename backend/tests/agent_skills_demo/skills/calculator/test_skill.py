"""Calculator Skill 单元测试"""

import pytest

from .scripts.impl import SkillImpl


@pytest.fixture
def skill() -> SkillImpl:
    return SkillImpl()


@pytest.mark.asyncio
async def test_simple_arithmetic(skill: SkillImpl) -> None:
    r = await skill.execute({"expression": "1+2"})
    assert r.success
    assert r.data["result"] == 3


@pytest.mark.asyncio
async def test_complex_expression(skill: SkillImpl) -> None:
    r = await skill.execute({"expression": "2 + 3 * 4"})
    assert r.success
    assert r.data["result"] == 14


@pytest.mark.asyncio
async def test_sqrt(skill: SkillImpl) -> None:
    r = await skill.execute({"expression": "sqrt(16)"})
    assert r.success
    assert r.data["result"] == 4


@pytest.mark.asyncio
async def test_missing_expression(skill: SkillImpl) -> None:
    r = await skill.execute({})
    assert not r.success
    assert "expression" in (r.error or "").lower() or "缺少" in (r.error or "")


@pytest.mark.asyncio
async def test_invalid_syntax(skill: SkillImpl) -> None:
    r = await skill.execute({"expression": "1 + "})
    assert not r.success
