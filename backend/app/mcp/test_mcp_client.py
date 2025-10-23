"""
在 backend 目录执行:
uv run -m app.mcp.test_mcp_client
"""
import os
import json
import asyncio
from .mcp_client import get_mcp_manager, MCPClientManager
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# 配置 logger 同时输出到控制台和日志文件
logger.add(
    Path(__file__).parent / "logs/{time:YYYY-MM-DD HH:mm:ss}.txt",
    level="INFO",
    format="| {time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8"
)


class UserMessage(BaseModel):
    message: str
    tool_calls: List[Dict[str, Any]]


async def execute_single_tool(tool_call: ChatCompletionMessageToolCall, mcp_client_manager: MCPClientManager):
    """
    执行单个工具调用
    """
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)
    logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")
    result = await mcp_client_manager.call_tool(tool_name, tool_args)
    logger.info(f"工具结果:")
    result_str = mcp_client_manager.format_mcp_result(result)
    logger.info(result_str[:200] + "..." + result_str[-200:]
                if len(result_str) > 200 else result_str)
    return result


async def chat_with_deepseek_single(
    mcp_client_manager: MCPClientManager,
    deepseek_client: AsyncOpenAI,
    user_message: UserMessage,
    tools: List[Dict[str, Any]],
    max_iterations: int = 5
) -> bool:
    # 初始化对话历史
    messages = [
        {"role": "user", "content": user_message.message}
    ]
    logger.info(f"用户: {user_message.message}")
    logger.info(f"{'='*60}\n")
    used_tools = {}

    for iteration in range(max_iterations):
        logger.info(f"--- 迭代 {iteration + 1} ---")

        # 调用 DeepSeek API
        response = await deepseek_client.chat.completions.create(
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
            logger.info(f"\n需要调用 {len(assistant_message.tool_calls)} 个工具:")

            # 执行所有工具调用
            tasks = []
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_arguments = json.loads(tool_call.function.arguments)
                used_tools[tool_name] = tool_arguments
                tasks.append(execute_single_tool(
                    tool_call, mcp_client_manager))
            tool_results = await asyncio.gather(*tasks)
            for tool_result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": mcp_client_manager.format_mcp_result(tool_result)
                })
        else:
            # 没有工具调用，返回最终答案
            final_response = assistant_message.content
            messages.append({
                "role": "assistant",
                "content": final_response
            })
            logger.info(f"\n{'='*60}")
            logger.info(f"DeepSeek 回复:")
            logger.info(final_response[:200] + "..." + final_response[-200:]
                        if len(final_response) > 200 else final_response)
            logger.info(f"{'='*60}\n")

    # 判断 UserMessage.tool_calls 列表中的每个工具 name 或 arguments 是否在 messages 中存在
    for tool_call in user_message.tool_calls:
        if tool_call['name'] not in used_tools:
            raise ValueError(f"未找到工具调用: {tool_call}")
        if tool_call.get('arguments') and tool_call['arguments'] not in used_tools[tool_call['name']]:
            raise ValueError(f"未找到工具调用参数: {tool_call['arguments']}")

    return True


async def chat_with_deepseek(
    mcp_client_manager: MCPClientManager,
    deepseek_client: AsyncOpenAI,
    user_messages: List[UserMessage],
    tools: List[Dict[str, Any]],
    max_iterations: int = 5
) -> List[bool]:
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
    tasks = []
    for user_message in user_messages:
        task = chat_with_deepseek_single(
            mcp_client_manager, deepseek_client, user_message, tools, max_iterations)
        tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


async def test_mcp_client():
    mcp_client_manager = await get_mcp_manager()
    tools = await mcp_client_manager.get_tools_for_llm()
    deepseek_client = AsyncOpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    logger.info(f"\n可用的 MCP 工具 ({len(tools)} 个):")
    for i, tool in enumerate(tools, 1):
        logger.info(
            f"{i}. {tool['function']['name']}: {tool['function']['description']}")

    # 4. 使用 DeepSeek API 调用工具
    logger.info("\n" + "="*60)
    logger.info("开始 DeepSeek + MCP Tools 演示")
    logger.info("="*60)

    # 查询 Confluence
    user_messages = [
        # UserMessage(
        #     message="请深入分析人工智能的发展趋势",
        #     tool_calls=[{
        #             "name": "tavily_search",
        #     }]),
        # UserMessage(
        #     message="搜索一下 2025 年人工智能的最新进展",
        #     tool_calls=[{
        #             "name": "tavily_search",
        #     }]),
        # UserMessage(
        #     message="请查询 Confluence 中关于 ai agent 的最新进展",
        #     tool_calls=[{
        #             "name": "confluence_search"
        #     }]
        # ),
        # UserMessage(
        #     message="请查询公司内部 ai agent 有关的项目",
        #     tool_calls=[{
        #             "name": "confluence_search"
        #     }]
        # ),
        UserMessage(
            message="请查询内部 ai agent 有关的项目",
            tool_calls=[{
                    "name": "confluence_search"
            }]
        ),
        # UserMessage(
        #     message="北京今天天气怎么样？",
        #     tool_calls=[{
        #             "name": "search_city",
        #     }]
        # )
    ]
    results = await chat_with_deepseek(
        mcp_client_manager=mcp_client_manager,
        deepseek_client=deepseek_client,
        user_messages=user_messages,
        tools=tools
    )
    # 判断 results 中正确的数量
    correct_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                f"第 {i+1} 个用户消息处理失败: {type(result).__name__}: {result}")
        elif result is True:
            correct_count += 1
    logger.info(f"成功处理的用户消息数量: {correct_count}")
    logger.info(f"失败处理的用户消息数量: {len(results) - correct_count}")


if __name__ == "__main__":
    asyncio.run(test_mcp_client())
