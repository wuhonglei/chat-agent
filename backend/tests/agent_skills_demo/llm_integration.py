"""
Agent Skills 的 LLM 集成模块

采用「按需读取 SKILL.md 并自主决定脚本调用」模式：
- LLM 通过 list_skills 了解可用技能
- 通过 read_skill_documentation 按需读取 SKILL.md 完整文档
- 阅读文档后自主决定是否、如何调用 execute_skill
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# 确保 skills 包可导入（支持从 backend 根目录运行 -m）
_demo_dir = Path(__file__).resolve().parent
if str(_demo_dir) not in sys.path:
    sys.path.insert(0, str(_demo_dir))

# 加载当前目录的 .env
try:
    from dotenv import load_dotenv

    load_dotenv(_demo_dir / ".env")
except ImportError:
    pass

from openai import AsyncOpenAI
from skills.base import SkillContext
from skills.registry import DocumentedSkillRegistry


def _meta_tool_definitions() -> list[dict[str, Any]]:
    """Meta-tools：让 LLM 按需读取 SKILL.md 并自主决定脚本调用"""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_skills",
                "description": "列出所有可用的 Agent Skill 及其简要描述。当需要了解有哪些技能可用时，先调用此工具。",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill_documentation",
                "description": "按需读取指定技能的完整 SKILL.md 文档（含 Instructions、Examples、参数 Schema）。在决定调用某个技能前，应先读取其文档以了解用法和参数格式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "技能名称，需与 list_skills 返回的 name 一致",
                        }
                    },
                    "required": ["skill_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_skill",
                "description": "执行指定的 Agent Skill。仅在阅读 read_skill_documentation 返回的 SKILL.md 并确认参数格式后调用。根据文档中的参数 Schema 传入 parameters。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "要执行的技能名称",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "根据 SKILL.md 中的参数 Schema 传入的参数字典",
                        },
                    },
                    "required": ["skill_name", "parameters"],
                },
            },
        },
    ]


class SkillLLMIntegration:
    """按需读取 SKILL.md 并自主决定脚本调用的 LLM 集成"""

    def __init__(
        self,
        registry: DocumentedSkillRegistry | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "deepseek-chat",
    ) -> None:
        self.registry = registry or DocumentedSkillRegistry(
            skills_dir=Path(__file__).parent / "skills"
        )
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", "sk-demo"),
            base_url=base_url
            or os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com"),
        )
        self.model = model
        self._tools = _meta_tool_definitions()

    async def _handle_tool_call(
        self, name: str, args: dict[str, Any], context: SkillContext
    ) -> dict[str, Any]:
        """处理 meta-tool 调用"""
        if name == "list_skills":
            skills = self.registry.list_skills()
            return {"skills": skills, "count": len(skills)}

        if name == "read_skill_documentation":
            skill_name = args.get("skill_name", "")
            doc = self.registry.get_skill_full_documentation(skill_name)
            if doc is None:
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' 未找到或无法读取文档",
                }
            return {"success": True, "documentation": doc}

        if name == "execute_skill":
            skill_name = args.get("skill_name", "")
            params = args.get("parameters") or {}
            skill = self.registry.get(skill_name)
            if not skill:
                return {"success": False, "error": f"Unknown skill: {skill_name}"}
            res = await skill.execute(params, context)
            return res.to_dict()

        return {"success": False, "error": f"Unknown tool: {name}"}

    async def chat(
        self,
        user_message: str,
        *,
        max_iterations: int = 5,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """
        处理用户消息：LLM 可选择调用 Skills，最终返回自然语言回复。

        Args:
            user_message: 用户输入
            max_iterations: 最大工具调用轮数
            user_id: 用户 ID（传入 SkillContext）
            session_id: 会话 ID（传入 SkillContext）

        Returns:
            LLM 的最终回复文本
        """
        self.registry.discover()
        if not self.registry.list_skills():
            return "未发现任何可用 Skill，请检查 skills 目录配置。"

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "你是一个智能助手，可以使用 Agent Skills 完成计算、天气查询、代码执行等任务。\n\n"
                "工作流程：\n"
                "1. 若不确定有哪些技能可用，先调用 list_skills 查看。\n"
                "2. 在调用某个技能前，必须先用 read_skill_documentation 读取其 SKILL.md 文档，了解 Instructions、Examples 和参数 Schema。\n"
                "3. 阅读文档后，若确认需要执行，再调用 execute_skill，按文档中的参数格式传入 parameters。\n"
                "4. 工具返回结果后，用自然语言组织回复给用户。",
            },
            {"role": "user", "content": user_message},
        ]

        context = SkillContext(user_id=user_id, session_id=session_id)

        for _ in range(max_iterations):
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self.model,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message

            if msg.content:
                messages.append({"role": "assistant", "content": msg.content})
            if msg.tool_calls:
                messages.append(msg.model_dump())
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    result = await self._handle_tool_call(name, args, context)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                continue

            # 无工具调用，返回最终回复
            return (msg.content or "").strip()

        return "达到最大迭代次数，请简化请求后重试。"


async def demo_main() -> None:
    """演示入口"""
    registry = DocumentedSkillRegistry(Path(__file__).parent / "skills")
    loaded = registry.discover()
    print(f"Loaded skills: {loaded}")

    integration = SkillLLMIntegration(registry=registry)

    # 示例：直接测试 calculator（不依赖 LLM）
    calc = registry.get("calculator")
    if calc:
        r = await calc.execute({"expression": "sqrt(16) + 2 * 3"})
        print(f"Calculator test: {r.to_dict()}")

    # 示例：LLM 对话（需要配置 API Key）
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        reply = await integration.chat("北京今天天气怎么样？")
        print(f"LLM reply: {reply}")
    else:
        print("跳过 LLM 调用（未设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY）")


if __name__ == "__main__":
    asyncio.run(demo_main())
