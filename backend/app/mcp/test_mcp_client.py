"""
在 backend 目录执行:
uv run -m app.mcp.test_mcp_client
"""
import os
import json
import asyncio
from .mcp_client import get_mcp_manager, MCPClientManager
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any
load_dotenv(Path(__file__).parent.parent.parent / ".env")


async def chat_with_deepseek(
    mcp_client_manager: MCPClientManager,
    deepseek_client: OpenAI,
    user_message: str,
    tools: List[Dict[str, Any]],
    max_iterations: int = 5
) -> str:
    """
    使用 DeepSeek API 处理对话，并在需要时调用 MCP 工具

    Args:
        mcp_client_manager: MCP 客户端管理器
        deepseek_client: DeepSeek API 客户端
        user_message: 用户消息
        tools: MCP 工具列表
        max_iterations: 最大迭代次数

    Returns:
        最终回复
    """

    # 初始化对话历史
    messages = [
        {"role": "user", "content": user_message}
    ]

    print(f"\n{'='*60}")
    print(f"用户: {user_message}")
    print(f"{'='*60}\n")

    # 迭代处理
    for iteration in range(max_iterations):
        print(f"--- 迭代 {iteration + 1} ---")

        # 调用 DeepSeek API
        response = deepseek_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=messages,
            tools=tools if tools else None
        )

        assistant_message = response.choices[0].message
        assistant_message_dict = assistant_message.model_dump(
            exclude_none=True)

        # 将助手消息添加到历史
        messages.append(assistant_message_dict)

        # 检查是否需要调用工具
        if assistant_message.tool_calls:
            print(f"\n需要调用 {len(assistant_message.tool_calls)} 个工具:")

            # 执行所有工具调用
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"\n调用工具: {tool_name}")
                print(
                    f"参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")

                # 执行 MCP 工具
                tool_result = await mcp_client_manager.call_tool(tool_name, tool_args)

                print(f'tool_result: {tool_result}')

                # 将工具结果添加到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": mcp_client_manager.format_mcp_result(tool_result)
                })
        else:
            # 没有工具调用，返回最终答案
            final_response = assistant_message.content
            print(f"\n{'='*60}")
            print(f"DeepSeek 回复: {final_response}")
            print(f"{'='*60}\n")
            return final_response

    return "达到最大迭代次数，未能获得最终答案"


async def test_mcp_client():
    mcp_client_manager = await get_mcp_manager()
    tools = await mcp_client_manager.get_tools_for_llm()
    deepseek_client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    print(f"\n可用的 MCP 工具 ({len(tools)} 个):")
    for i, tool in enumerate(tools, 1):
        print(
            f"{i}. {tool['function']['name']}: {tool['function']['description']}")

    # 4. 使用 DeepSeek API 调用工具
    print("\n" + "="*60)
    print("开始 DeepSeek + MCP Tools 演示")
    print("="*60)

    await chat_with_deepseek(
        mcp_client_manager=mcp_client_manager,
        deepseek_client=deepseek_client,
        user_message="请深入分析人工智能的发展趋势",
        tools=tools
    )

    # 示例 1: 搜索并查询
    await chat_with_deepseek(
        mcp_client_manager=mcp_client_manager,
        deepseek_client=deepseek_client,
        user_message="搜索一下 2025 年人工智能的最新进展, 并深入分析开发者应如何把握这些机会",
        tools=tools
    )

    # 示例 2: 查询天气
    await chat_with_deepseek(
        mcp_client_manager=mcp_client_manager,
        deepseek_client=deepseek_client,
        user_message="北京今天天气怎么样？",
        tools=tools
    )


if __name__ == "__main__":
    asyncio.run(test_mcp_client())
