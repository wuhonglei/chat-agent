"""
MCP Client - 演示如何同时连接远程和本地 MCP 服务器
最简单的方案：使用 MCPConfigTransport 自动合并多个远程服务器 + 本地服务器挂载
结合 DeepSeek API 调用 MCP Tools
"""

import asyncio
import json
import os
from typing import List, Dict, Any
from openai import OpenAI
from fastmcp import Client
from fastmcp.client.transports import MCPConfig
import time


def convert_mcp_tools_to_openai_format(mcp_tools) -> List[Dict[str, Any]]:
    """
    将 MCP 工具格式转换为 OpenAI/DeepSeek 工具格式

    Args:
        mcp_tools: MCP 工具列表

    Returns:
        OpenAI 格式的工具列表
    """
    openai_tools = []

    for tool in mcp_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
            }
        }

        # 添加参数定义
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            openai_tool["function"]["parameters"] = tool.inputSchema
        else:
            # 如果没有参数定义，使用空对象
            openai_tool["function"]["parameters"] = {
                "type": "object",
                "properties": {},
                "required": []
            }

        openai_tools.append(openai_tool)

    return openai_tools


async def execute_mcp_tool(client: Client, tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    执行 MCP 工具

    Args:
        client: MCP 客户端
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    try:
        result = await client.call_tool(tool_name, arguments)

        # 处理结果
        if hasattr(result, 'content'):
            # 如果结果有 content 属性
            if isinstance(result.content, list):
                # 如果是列表，提取所有文本内容
                text_parts = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                return "\n".join(text_parts)
            elif hasattr(result.content, 'text'):
                return result.content.text
            else:
                return str(result.content)
        else:
            return str(result)
    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"


async def chat_with_deepseek(
    client: Client,
    deepseek_client: OpenAI,
    user_message: str,
    mcp_tools: list,
    max_iterations: int = 5
) -> str:
    """
    使用 DeepSeek API 处理对话，并在需要时调用 MCP 工具

    Args:
        client: MCP 客户端
        deepseek_client: DeepSeek API 客户端
        user_message: 用户消息
        mcp_tools: MCP 工具列表
        max_iterations: 最大迭代次数

    Returns:
        最终回复
    """
    # 转换工具格式
    openai_tools = convert_mcp_tools_to_openai_format(mcp_tools)

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
            model="deepseek-chat",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # 将助手消息添加到历史
        messages.append(assistant_message)

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
                tool_result = await execute_mcp_tool(client, tool_name, tool_args)

                print(f"结果: {tool_result[:200]}..." if len(
                    tool_result) > 200 else f"结果: {tool_result}")

                # 将工具结果添加到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            # 没有工具调用，返回最终答案
            final_response = assistant_message.content
            print(f"\n{'='*60}")
            print(f"DeepSeek 回复: {final_response}")
            print(f"{'='*60}\n")
            return final_response

    return "达到最大迭代次数，未能获得最终答案"


async def main():
    """Main function"""
    start_time = time.time()

    # 1. 配置 MCP 服务器
    config = {
        "mcpServers": {
            "tavily-remote-mcp": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "http",
            },
            "weather-mcp": {
                "command": "uv",
                "args": ["run", "-m", "mcp_demo.weather_mcp.weather_server", "--transport", "stdio"],
                "env": {
                    "QWEATHER_API_KEY": os.getenv("QWEATHER_API_KEY", "32de48c2fba5456cb0239c6b4f7d29ac"),
                    "QWEATHER_BASE_URL": os.getenv("QWEATHER_BASE_URL", "https://pb6hewdvet.re.qweatherapi.com"),
                    "QWEATHER_TIMEOUT":  os.getenv("QWEATHER_TIMEOUT", "10"),
                }
            }
        }
    }

    mcp_config = MCPConfig.from_dict(config)
    client = Client(transport=mcp_config)

    # 2. 初始化 DeepSeek 客户端
    deepseek_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY",
                          "sk-00e90cb4d67e4c51b0d1cef72e604800"),
        base_url="https://api.deepseek.com/v1"
    )

    async with client:
        # 3. 获取 MCP 工具列表
        print("正在获取 MCP 工具列表...")
        tools = await client.list_tools()

        print(f"\n可用的 MCP 工具 ({len(tools)} 个):")
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.name}: {tool.description}")

        # 4. 使用 DeepSeek API 调用工具
        print("\n" + "="*60)
        print("开始 DeepSeek + MCP Tools 演示")
        print("="*60)

        # 示例 1: 查询天气
        await chat_with_deepseek(
            client=client,
            deepseek_client=deepseek_client,
            user_message="北京今天天气怎么样？",
            mcp_tools=tools
        )

        print("\n" + "="*60)

        # 示例 2: 搜索并查询
        await chat_with_deepseek(
            client=client,
            deepseek_client=deepseek_client,
            user_message="搜索一下 2024 年人工智能的最新进展",
            mcp_tools=tools
        )

        end_time = time.time()
        print(f"\n总耗时: {end_time - start_time:.2f} 秒")


if __name__ == "__main__":
    asyncio.run(main())
