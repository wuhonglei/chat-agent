"""
Agent Skills Demo - 使用 AsyncOpenAI 与 agent skills 的示例

- System prompt 仅包含 skill 的 name、description、skill.md 路径
- 通过 view_text_file、execute_shell_command、execute_python_code 自主读取 skill 并执行
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
from typing import Any

import yaml
from openai import AsyncOpenAI

from tests.agent_skills_demo.tools import execute_tool, get_tools
from tests.agent_skills_demo.tools._common import SKILLS_DIR


def load_skills(skills_dir: Path = SKILLS_DIR) -> list[dict[str, str]]:
    """扫描 skill 目录，解析 SKILL.md frontmatter"""
    skills: list[dict[str, str]] = []
    for skill_md in skills_dir.rglob("SKILL.md"):
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue
        if not content.strip().startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1])
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        name = meta.get("name") or meta.get("title") or skill_md.parent.name
        desc = meta.get("description") or ""
        base = skills_dir.parent  # agent_skills_demo 根目录
        skill_md_path = str(skill_md.relative_to(base))
        skill_cwd = str(skill_md.parent.relative_to(base))
        skills.append(
            {
                "name": str(name),
                "description": str(desc),
                "skill_md_path": skill_md_path,
                "skill_cwd": skill_cwd,
            }
        )
    return skills


def build_system_prompt(skills: list[dict[str, str]]) -> str:
    """构建 system prompt，仅包含 name、description、skill.md 路径"""
    lines = [
        "You are a helpful assistant with access to agent skills. You can use the skills to help you answer questions and perform tasks.",
        "# Agent Skills",
        "The agent skills are a collection of folds of instructions, scripts, and resources that you can load dynamically to improve performance on specialized tasks. Each agent skill has a `SKILL.md` file in its folder that describes how to use the skill. If you want to use a skill, you MUST read its `SKILL.md` file carefully.",
        "",
    ]
    for s in skills:
        lines.append(
            (
                f"## {s['name']}\n"
                f"{s['description']}\n"
                f'Check "{s["skill_md_path"]}" for how to use this skill.'
            ),
        )
    return "\n".join(lines)


async def chat_with_agent(
    client: AsyncOpenAI,
    system_prompt: str,
    user_message: str,
    model: str = "deepseek-chat",
    max_iterations: int = 10,
) -> str:
    """Agent 循环：调用 LLM，处理 tool_calls"""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tools = get_tools()

    for iteration in range(max_iterations):
        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not getattr(msg, "tool_calls", None):
            return (msg.content or "").strip()

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            print(f"[工具调用] name={name} args={args}")
            result = execute_tool(name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    return "达到最大迭代次数，未能获得最终答案"


async def main() -> None:
    """主入口"""
    skills = load_skills()
    print(f"已加载 {len(skills)} 个 skill:")
    for s in skills:
        print(f"  - {s['name']}: {s['skill_md_path']}")

    system_prompt = build_system_prompt(skills)
    print(f"system_prompt: {system_prompt}")

    client = AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "sk-placeholder"),
        base_url=os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
    )

    user_message = "查询今日新闻"
    print(f"\n用户: {user_message}\n")
    result = await chat_with_agent(client, system_prompt, user_message)
    print(f"助手: {result}\n")


if __name__ == "__main__":
    asyncio.run(main())
