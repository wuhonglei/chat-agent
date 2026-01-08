"""Token 计算和消息截断工具"""
import json
from typing import Any

import tiktoken
from app.utils.logger import logger


def get_max_context_tokens(model: str) -> int:
    """
    获取模型的最大上下文 token 数量

    Args:
        model: 模型名称

    Returns:
        最大上下文 token 数量
    """
    # 常见模型的上下文限制
    model_limits = {
        "deepseek-chat": 131072,
        "deepseek-reasoner": 131072,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16385,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
    }

    # 检查模型名称是否包含已知的模型标识
    for model_key, limit in model_limits.items():
        if model_key in model.lower():
            return limit

    # 默认值：131072（deepseek 的默认限制）
    return 131072  # 131k


def count_tokens_for_messages(messages: list[dict[str, Any]], model: str = "gpt-4") -> int:
    """
    计算消息列表的 token 数量

    Args:
        messages: 消息列表
        model: 模型名称，用于选择正确的编码器

    Returns:
        token 数量
    """
    try:
        # 根据模型选择编码器，默认使用 cl100k_base（GPT-4 和大多数现代模型使用）
        # 对于 deepseek 模型，也使用 cl100k_base
        encoding_name = "cl100k_base"

        # 尝试获取编码器
        try:
            encoding = tiktoken.get_encoding(encoding_name)
        except KeyError:
            # 如果编码器不存在，使用默认的
            encoding = tiktoken.encoding_for_model(model)

        total_tokens = 0

        for message in messages:
            # 每个消息都有一些基础 token（角色、格式等）
            # 根据 OpenAI 的文档，每条消息大约有 4 个额外 token
            total_tokens += 4

            # 计算消息内容的 token
            if isinstance(message, dict):
                # 处理 content 字段
                content = message.get("content")
                if content and isinstance(content, str):
                    total_tokens += len(encoding.encode(content))

                # 处理 reasoning_content 字段（如果存在）
                reasoning_content = message.get("reasoning_content")
                if reasoning_content and isinstance(reasoning_content, str):
                    total_tokens += len(encoding.encode(reasoning_content))

                # 处理 tool_calls 字段
                tool_calls = message.get("tool_calls")
                if tool_calls:
                    # 将 tool_calls 序列化为 JSON 来计算 token
                    tool_calls_str = json.dumps(tool_calls, ensure_ascii=False)
                    total_tokens += len(encoding.encode(tool_calls_str))
                    # tool_calls 有额外的格式开销，每条大约 12 个 token
                    total_tokens += len(tool_calls) * 12
            else:
                # 如果不是字典，尝试转换为字符串
                message_str = str(message)
                total_tokens += len(encoding.encode(message_str))

        # 回复本身也需要预留一些 token（通常预留 1000-2000）
        # 这里不预留，因为我们要确保所有消息都在限制内

        return total_tokens
    except Exception as e:
        logger.error("Failed to count tokens", error=e, model=model)
        # 如果计算失败，使用粗略估算：1 token ≈ 4 个字符
        total_chars = sum(len(json.dumps(msg, ensure_ascii=False))
                          for msg in messages)
        return total_chars // 4


def truncate_messages(
    messages: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4",
    preserve_system: bool = True,
    preserve_user: bool = True,
) -> list[dict[str, Any]]:
    """
    截断消息列表，确保不超过 token 限制

    策略：保持消息的原始顺序，从前往后截断（保留最新的消息）
    1. 始终保留 system message（如果存在）
    2. 始终保留最后一个 user message 及其后的所有消息（如果 preserve_user=True）
    3. 从最旧的历史消息开始移除，直到满足 token 限制
    4. 如果工具调用结果太长，截断其内容

    Args:
        messages: 消息列表
        max_tokens: 最大 token 数量
        model: 模型名称
        preserve_system: 是否保留 system message
        preserve_user: 是否保留最后一个 user message 及其后的消息

    Returns:
        截断后的消息列表
    """
    if not messages:
        return messages

    current_tokens = count_tokens_for_messages(messages, model)

    if current_tokens <= max_tokens:
        logger.debug(
            "Messages within token limit",
            current_tokens=current_tokens,
            max_tokens=max_tokens,
        )
        return messages

    logger.warning(
        "Messages exceed token limit, truncating",
        current_tokens=current_tokens,
        max_tokens=max_tokens,
        messages_count=len(messages),
    )

    # 找到最后一个 user message 的位置
    last_user_index = -1
    if preserve_user:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_index = i
                break

    # 分离消息：需要保留的部分和可以截断的部分
    # 1. system messages（如果 preserve_system=True）
    system_start = 0
    system_end = 0
    if preserve_system and messages:
        if messages[0].get("role") == "system":
            system_end = 1
            # 可能有多个 system messages
            while system_end < len(messages) and messages[system_end].get("role") == "system":
                system_end += 1

    # 2. 需要保留的部分（最后一个 user message 及其后的所有消息）
    preserve_start = last_user_index if last_user_index >= 0 else len(messages)

    # 3. 可以截断的历史消息（system 之后到 preserve_start 之前）
    history_messages = messages[system_end:preserve_start] if preserve_start > system_end else [
    ]
    preserve_messages = messages[preserve_start:] if preserve_start >= 0 else [
    ]

    # 计算需要保留的消息的 token
    system_tokens = count_tokens_for_messages(
        messages[system_start:system_end], model) if system_end > system_start else 0
    preserve_tokens = count_tokens_for_messages(
        preserve_messages, model) if preserve_messages else 0
    remaining_tokens = max_tokens - system_tokens - preserve_tokens

    if remaining_tokens < 0:
        # 即使只保留 system 和最后的消息也超过限制，需要截断工具调用结果
        logger.warning(
            "Even preserved messages exceed limit, truncating tool call results",
            system_tokens=system_tokens,
            preserve_tokens=preserve_tokens,
            max_tokens=max_tokens,
        )
        # 截断 preserve_messages 中的工具调用结果
        truncated_preserve = truncate_tool_results_in_messages(
            preserve_messages, max_tokens - system_tokens, model)
        result = messages[system_start:system_end] + truncated_preserve
    else:
        # 从历史消息中选择可以保留的部分（从后往前，保留最近的）
        kept_history = []
        for msg in reversed(history_messages):
            msg_tokens = count_tokens_for_messages([msg], model)
            if msg_tokens <= remaining_tokens:
                kept_history.insert(0, msg)
                remaining_tokens -= msg_tokens
            else:
                # 如果单条消息就超过限制，尝试截断其内容
                truncated_msg = truncate_message_content(
                    msg, remaining_tokens, model)
                if truncated_msg:
                    kept_history.insert(0, truncated_msg)
                break

        # 构建最终结果
        result = (
            messages[system_start:system_end] +
            kept_history +
            preserve_messages
        )

    final_tokens = count_tokens_for_messages(result, model)
    logger.info(
        "Messages truncated",
        original_tokens=current_tokens,
        final_tokens=final_tokens,
        max_tokens=max_tokens,
        original_count=len(messages),
        final_count=len(result),
    )

    return result


def truncate_tool_results_in_messages(
    messages: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4",
) -> list[dict[str, Any]]:
    """
    截断消息列表中的工具调用结果内容

    Args:
        messages: 消息列表
        max_tokens: 最大 token 数量
        model: 模型名称

    Returns:
        截断后的消息列表
    """
    result = []
    remaining_tokens = max_tokens

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except KeyError:
        encoding = tiktoken.encoding_for_model(model)

    for msg in messages:
        role = msg.get("role", "")

        if role == "tool":
            # 截断 tool 消息的内容
            content = msg.get("content", "")
            if content:
                # 计算基础 token（role, tool_call_id 等，约 20 个）
                base_tokens = 20
                available_tokens = max(0, remaining_tokens - base_tokens)

                if available_tokens > 0:
                    content_tokens = len(encoding.encode(content))
                    if content_tokens > available_tokens:
                        # 截断内容
                        truncated_content = truncate_text_by_tokens(
                            content, available_tokens, encoding)
                        truncated_msg = msg.copy()
                        truncated_msg["content"] = (
                            truncated_content + "\n\n[内容已截断，仅保留关键信息]"
                        )
                        result.append(truncated_msg)
                        remaining_tokens -= (
                            len(encoding.encode(truncated_content)) + base_tokens)
                    else:
                        result.append(msg)
                        remaining_tokens -= (content_tokens + base_tokens)
                else:
                    # 没有空间了，跳过这个 tool 消息
                    continue
            else:
                result.append(msg)
        else:
            # 非 tool 消息，计算 token 并添加
            msg_tokens = count_tokens_for_messages([msg], model)
            if msg_tokens <= remaining_tokens:
                result.append(msg)
                remaining_tokens -= msg_tokens
            else:
                # 尝试截断内容
                truncated_msg = truncate_message_content(
                    msg, remaining_tokens, model)
                if truncated_msg:
                    result.append(truncated_msg)
                break

    return result


def truncate_message_content(
    message: dict[str, Any],
    max_tokens: int,
    model: str = "gpt-4",
) -> dict[str, Any] | None:
    """
    截断单条消息的内容

    Args:
        message: 消息字典
        max_tokens: 最大 token 数量
        model: 模型名称

    Returns:
        截断后的消息字典，如果无法截断则返回 None
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except KeyError:
        encoding = tiktoken.encoding_for_model(model)

    # 计算消息的基础 token（role 等，约 4 个）
    base_tokens = 4
    available_tokens = max(0, max_tokens - base_tokens)

    if available_tokens <= 0:
        return None

    truncated_msg = message.copy()

    # 截断 content
    content = message.get("content")
    if content and isinstance(content, str):
        content_tokens = len(encoding.encode(content))
        if content_tokens > available_tokens:
            truncated_content = truncate_text_by_tokens(
                content, available_tokens, encoding)
            truncated_msg["content"] = truncated_content + "\n\n[内容已截断]"
        # 如果 content 在限制内，不需要修改

    # 截断 reasoning_content（如果存在）
    reasoning_content = message.get("reasoning_content")
    if reasoning_content and isinstance(reasoning_content, str):
        # reasoning_content 通常可以完全移除或大幅截断
        reasoning_tokens = len(encoding.encode(reasoning_content))
        if reasoning_tokens > available_tokens // 2:  # 只保留一半空间给 reasoning
            truncated_reasoning = truncate_text_by_tokens(
                reasoning_content, available_tokens // 2, encoding
            )
            truncated_msg["reasoning_content"] = truncated_reasoning + \
                "\n\n[推理内容已截断]"

    return truncated_msg


def truncate_tool_call_pair(
    assistant_msg: dict[str, Any],
    tool_msgs: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4",
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """
    截断工具调用对的内容，确保不超过 token 限制

    Args:
        assistant_msg: assistant 消息
        tool_msgs: 对应的 tool 消息列表
        max_tokens: 最大 token 数量
        model: 模型名称

    Returns:
        截断后的 (assistant_msg, tool_msgs) 或 None（如果无法截断到限制内）
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except KeyError:
        encoding = tiktoken.encoding_for_model(model)

    # 计算 assistant 消息的 token
    assistant_tokens = count_tokens_for_messages([assistant_msg], model)

    if assistant_tokens >= max_tokens:
        # assistant 消息本身就超过限制，无法截断
        return None

    remaining_tokens = max_tokens - assistant_tokens

    # 截断 tool 消息的内容
    truncated_tool_msgs = []
    for tool_msg in tool_msgs:
        content = tool_msg.get("content", "")
        if not content:
            truncated_tool_msgs.append(tool_msg)
            continue

        # 计算当前内容的 token
        content_tokens = len(encoding.encode(content))

        # 为每个 tool 消息预留基础 token（role, tool_call_id 等，约 20 个）
        tool_base_tokens = 20

        if content_tokens + tool_base_tokens <= remaining_tokens:
            # 可以完整保留
            truncated_tool_msgs.append(tool_msg)
            remaining_tokens -= (content_tokens + tool_base_tokens)
        else:
            # 需要截断内容
            available_tokens = max(0, remaining_tokens - tool_base_tokens)
            if available_tokens <= 0:
                # 没有空间了，跳过这个 tool 消息
                continue

            # 截断内容
            truncated_content = truncate_text_by_tokens(
                content, available_tokens, encoding)

            truncated_tool_msg = tool_msg.copy()
            truncated_tool_msg["content"] = (
                truncated_content + "\n\n[内容已截断，仅保留关键信息]"
            )
            truncated_tool_msgs.append(truncated_tool_msg)
            remaining_tokens -= (len(encoding.encode(truncated_content)
                                     ) + tool_base_tokens)

    return (assistant_msg, truncated_tool_msgs)


def truncate_text_by_tokens(text: str, max_tokens: int, encoding: tiktoken.Encoding) -> str:
    """
    按 token 数量截断文本

    Args:
        text: 要截断的文本
        max_tokens: 最大 token 数量
        encoding: tiktoken 编码器

    Returns:
        截断后的文本
    """
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # 截断到 max_tokens
    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)
