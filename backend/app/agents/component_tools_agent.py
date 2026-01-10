"""Component Tools Agent for handling component tool calls"""
import json
from collections.abc import AsyncGenerator
from typing import Any, Optional, cast

from jsonschema import validate, ValidationError as JsonSchemaValidationError
from openai.types.chat import ChatCompletionMessage

from app.schemas.chat import ComponentToolConfig
from app.schemas.config import LLMConfig
from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.utils.logger import logger
from app.utils.message import format_tool_call_messages_for_llm, normalize_message_to_dict
from app.schemas.token_stats import ComponentToolsTokenStats
from app.utils.time import get_current_time, get_time_duration
from app.services.component_schema_service import ComponentSchemaService
from app.utils.component_tools import convert_schema_to_tool_definition
from app.prompts.prompt_utils import get_prompt_for_component_render_data
from app.agents.base import BaseAgent


class ComponentToolsAgent(BaseAgent):
    """组件工具调用Agent - 负责处理组件工具调用逻辑"""

    def __init__(self, llm_config: LLMConfig, schema_service: ComponentSchemaService, think_mode: bool = False):
        super().__init__(llm_config, think_mode)
        self.schema_service = schema_service
        self.collected_messages: list[ToolCallMessage] = []
        self.token_stats: Optional[ComponentToolsTokenStats] = None
        self.duration: Optional[float] = None

    def create_token_stats(
        self,
        component_messages: list[dict],
    ) -> ComponentToolsTokenStats:
        """创建组件工具调用的 token 统计对象

        Args:
            component_messages: 组件消息列表（用于计算 prompt_tokens）

        Returns:
            ComponentToolsTokenStats: token 统计对象
        """
        # 计算输入 token（系统提示 + 用户消息 + MCP工具上下文）
        prompt_tokens = self.token_calculator.count_messages_tokens(
            component_messages)

        # 计算组件工具的输出token（助手消息 + 工具调用结果）
        completion_tokens = self.token_calculator.count_messages_tokens(
            self.collected_messages
        )

        return ComponentToolsTokenStats(
            model_name=self.model,
            agent_name="component_tools_agent",
            token_usage=self._create_token_usage(
                prompt_tokens, completion_tokens),
        )

    async def stream_execute(
        self,
        user_message: str,
        mcp_tool_call_messages: list[ToolCallMessage],
        component_tools_for_backend: list[ComponentToolConfig],
    ) -> AsyncGenerator[str, None]:
        """
        流式执行组件工具调用并返回SSE消息

        Args:
            user_message: 用户消息
            mcp_tool_call_messages: MCP工具调用消息列表
            component_tools_for_backend: 组件工具配置列表

        Yields:
            str: SSE格式的消息
        """
        if not component_tools_for_backend:
            return

        # 提取MCP工具信息
        mcp_tool_names, mcp_tool_call_contents = self._extract_mcp_tool_info(
            mcp_tool_call_messages
        )

        # 根据条件过滤组件工具
        filtered_component_tools = []
        for component_config in component_tools_for_backend:
            if self._check_component_condition(
                component_config,
                mcp_tool_names,
                mcp_tool_call_contents,
                user_message,
            ):
                filtered_component_tools.append(component_config.name)
                logger.info(
                    "Component tool condition satisfied",
                    component_name=component_config.name,
                )
            else:
                logger.info(
                    "Component tool condition not satisfied, skipping",
                    component_name=component_config.name,
                )

        if not filtered_component_tools:
            self.token_stats = None
            logger.info(
                "No component tools passed condition check",
                total_components=len(component_tools_for_backend),
            )
            return

        # 准备消息列表
        system_prompt, component_user_message = get_prompt_for_component_render_data(
            user_message)
        component_messages = self._compose_messages(
            system_prompt, [], component_user_message, mcp_tool_call_messages
        )

        # 初始化 token 统计
        start_time = get_current_time()
        async for message in self._call_llm_with_component_tools(
            component_messages, self.model, self.extra_body, filtered_component_tools
        ):
            if message:
                yield self.format_sse_message('component_tool_call', message.model_dump())

        if self.collected_messages:
            self.duration = get_time_duration(start_time)
            # 创建token统计对象（内部进行所有token计算）
            self.token_stats = self.create_token_stats(
                component_messages=component_messages,
            )
            yield self.format_sse_message('component_tool_call', {
                'status': 'done',
                'duration': self.duration,
            })

    def _check_component_condition(
        self,
        component_config: ComponentToolConfig,
        mcp_tool_names: list[str],
        mcp_tool_call_contents: list[str],
        user_message: str,
    ) -> bool:
        """检查组件是否满足条件

        Args:
            component_config: 组件配置
            mcp_tool_names: 已调用的 MCP 工具名称列表
            mcp_tool_call_contents: MCP 工具响应内容列表
            user_message: 用户消息内容

        Returns:
            bool: 是否满足条件
        """
        when = component_config.when
        when_condition = component_config.when_condition

        # 收集所有条件的匹配结果
        condition_results = []

        # 检查 mcp_tool_names 条件
        if when.mcp_tool_names is not None:
            # 检查是否有任何已调用的工具名称部分包含匹配
            matched = any(
                any(expected_tool in actual_tool for actual_tool in mcp_tool_names)
                for expected_tool in when.mcp_tool_names
            )
            condition_results.append(matched)
            logger.debug(
                "Checking mcp_tool_names condition",
                component_name=component_config.name,
                expected_tools=when.mcp_tool_names,
                actual_tools=mcp_tool_names,
                matched=matched,
            )

        # 检查 mcp_tool_call_content 条件
        if when.mcp_tool_call_content is not None:
            # 检查是否有任何工具响应内容包含指定的字符串
            matched = any(
                any(keyword in content for content in mcp_tool_call_contents)
                for keyword in when.mcp_tool_call_content
            )
            condition_results.append(matched)
            logger.debug(
                "Checking mcp_tool_call_content condition",
                component_name=component_config.name,
                expected_keywords=when.mcp_tool_call_content,
                matched=matched,
            )

        # 检查 user_message 条件
        if when.user_message is not None:
            # 检查用户消息是否包含指定的字符串
            matched = when.user_message in user_message
            condition_results.append(matched)
            logger.debug(
                "Checking user_message condition",
                component_name=component_config.name,
                expected_keyword=when.user_message,
                matched=matched,
            )

        # 如果没有设置任何条件，默认返回 True（允许调用）
        if not condition_results:
            logger.debug(
                "No conditions set, allowing component",
                component_name=component_config.name,
            )
            return True

        # 根据 when_condition 决定组合逻辑
        if when_condition == "and":
            # 所有条件都必须满足
            result = all(condition_results)
        else:  # "or"
            # 至少一个条件满足即可
            result = any(condition_results)

        logger.info(
            "Component condition check result",
            component_name=component_config.name,
            when_condition=when_condition,
            condition_results=condition_results,
            result=result,
        )

        return result

    def _extract_mcp_tool_info(
        self,
        mcp_tool_call_messages: list[ToolCallMessage],
    ) -> tuple[list[str], list[str]]:
        """从 MCP 工具调用消息中提取工具名称和响应内容

        Args:
            mcp_tool_call_messages: MCP 工具调用消息列表

        Returns:
            tuple[list[str], list[str]]: (工具名称列表, 工具响应内容列表)
        """
        tool_names: list[str] = []
        tool_call_contents: list[str] = []

        for message in mcp_tool_call_messages:
            if isinstance(message, AssistantToolCallMessage) and message.tool_calls:
                # 从 assistant 消息中提取工具名称
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_names.append(tool_name)
            elif isinstance(message, ToolCallResultMessage) and not message.is_error:
                # 从 tool 消息中提取响应内容
                tool_call_contents.append(message.content)

        return tool_names, tool_call_contents

    async def _call_llm_with_component_tools(
        self,
        # system message + user_message + mcp tool messages
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
        component_tool_names: list[str],
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with component tools and collect component data

        Args:
            messages: 包含 system message、user message 和 MCP tool call messages 的消息列表
            model: LLM 模型名称
            extra_body: 模型额外参数
            component_tool_names: 组件工具名称列表（例如：['weather']）

        Yields:
            ToolCallMessage: 工具调用相关的消息
        """
        if not component_tool_names:
            return

        # 获取并转换组件工具的 JSON schema 为 LLM tool 定义格式
        try:
            schemas = await self.schema_service.get_schemas(component_tool_names)
        except Exception as e:
            logger.error(
                "Failed to get component schemas",
                component_tool_names=component_tool_names,
                error=e,
            )
            return

        if not schemas:
            logger.warning(
                "No schemas retrieved",
                component_tool_names=component_tool_names,
            )
            return

        # 将 JSON schemas 转换为 LLM tool 定义
        component_tools = []
        for component_tool_name, json_schema in schemas.items():
            try:
                tool_definition = convert_schema_to_tool_definition(
                    component_tool_name, json_schema
                )
                component_tools.append(tool_definition)
                logger.info(
                    "Component tool definition created",
                    component_tool_name=component_tool_name,
                )
            except Exception as e:
                logger.error(
                    "Failed to convert schema to tool definition",
                    component_tool_name=component_tool_name,
                    error=e,
                )
                continue

        if not component_tools:
            logger.warning("No component tools created")
            return

        # 调用 LLM API，让 LLM 决定是否调用组件工具
        max_iterations = len(component_tools)  # 组件工具调用最多迭代次数

        for iteration in range(max_iterations):
            logger.info(
                "Component tool call iteration started",
                iteration=iteration + 1,
                max_iterations=max_iterations,
            )

            # 调用 LLM
            # 格式化 collected_messages，过滤掉额外的字段（如 token_count, duration, is_error）
            formatted_collected_messages = format_tool_call_messages_for_llm(
                self.collected_messages, clear_reasoning_content=False)
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages + formatted_collected_messages,
                tools=component_tools,
                stream=False,
                extra_body=extra_body,
            )
            openai_message: ChatCompletionMessage = response.choices[0].message

            if not openai_message.tool_calls:
                logger.info(
                    "No component tool calls needed",
                    has_content=bool(openai_message.content),
                )
                return

            # 处理组件工具调用
            reasoning_content = hasattr(
                openai_message, 'reasoning_content') and openai_message.reasoning_content or None
            assistant_message = AssistantToolCallMessage(**{
                'role': 'assistant',
                'content': openai_message.content,
                'tool_calls': openai_message.tool_calls,
                'reasoning_content': reasoning_content,
            })
            self.collected_messages.append(assistant_message)
            yield assistant_message

            tool_count = len(assistant_message.tool_calls)
            logger.info(
                "Component tool calls required",
                tool_count=tool_count,
                iteration=iteration + 1,
            )

            # 收集组件工具调用的结果
            for tool_call in assistant_message.tool_calls:
                tool_name = cast(str, tool_call.function.name)
                component_name_prefix = "generate_component_"
                # 提取组件名称（去掉 generate_component_ 前缀）
                component_tool_name = tool_name.replace(
                    component_name_prefix, "")
                if component_tool_name not in schemas:
                    logger.warning(
                        "Component schema not found",
                        tool_name=tool_name,
                        component_tool_name=component_tool_name,
                        tool_call_id=tool_call.id,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": f"Component schema not found for tool {tool_name}, skipping",
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_messages.append(tool_call_result_message)
                    yield tool_call_result_message
                    continue

                # 解析工具调用的 arguments
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    schema = schemas[component_tool_name]
                    validate(instance=arguments, schema=schema)
                    logger.debug(
                        "Component tool call arguments validated",
                        tool_name=tool_name,
                        arguments=arguments,
                        tool_call_id=tool_call.id,
                    )
                    # 创建工具调用结果消息
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": False,
                        "content": "Component data generated successfully",
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_messages.append(tool_call_result_message)
                    yield tool_call_result_message

                    # 从 component_tools 中移除已成功构造的组件
                    component_tools[:] = [
                        tool for tool in component_tools
                        if tool.get("function", {}).get("name") != tool_name
                    ]
                    logger.debug(
                        "Component tool removed from list",
                        tool_name=tool_name,
                        remaining_tools=len(component_tools),
                    )
                except JsonSchemaValidationError as e:
                    error_msg = f"JSON schema validation failed: {e.message}"
                    logger.warning(
                        "Component tool call arguments validation failed",
                        tool_name=tool_name,
                        component_tool_name=component_tool_name,
                        tool_call_id=tool_call.id,
                        validation_error=error_msg,
                        arguments=arguments,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": error_msg,
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_messages.append(tool_call_result_message)
                    yield tool_call_result_message
                    continue

        logger.info(
            "Component tool call iterations completed",
            max_iterations=max_iterations,
        )
        return
