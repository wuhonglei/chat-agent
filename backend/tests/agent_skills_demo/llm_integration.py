"""
Agent Skills 的 LLM 集成模块

将 Skills 作为工具暴露给 LLM，实现「用户自然语言 -> LLM 选择 Skill -> 执行 -> 返回结果」的流程。
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


class SkillLLMIntegration:
    """将 Skills 作为工具与 LLM 集成的处理器"""

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
        self._tools: list[dict[str, Any]] | None = None

    def _get_tools(self) -> list[dict[str, Any]]:
        """获取 LLM 工具定义（延迟加载）"""
        if self._tools is None:
            self.registry.discover()
            self._tools = self.registry.to_tool_definitions()
        return self._tools

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
        tools = self._get_tools()
        if not tools:
            return "未发现任何可用 Skill，请检查 skills 目录配置。"

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "你是一个智能助手，可以根据用户需求调用计算器、天气查询、代码执行等工具。"
                "当用户需要计算、查天气或执行代码时，请调用相应工具。"
                "工具返回结果后，用自然语言组织回复给用户。",
            },
            {"role": "user", "content": user_message},
        ]

        context = SkillContext(user_id=user_id, session_id=session_id)

        for _ in range(max_iterations):
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self.model,
                messages=messages,
                tools=tools,
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

                    skill = self.registry.get(name)
                    if not skill:
                        result = {"success": False, "error": f"Unknown skill: {name}"}
                    else:
                        res = await skill.execute(args, context)
                        result = res.to_dict()

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
