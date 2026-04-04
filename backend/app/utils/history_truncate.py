"""历史消息按轮数与 token 截断"""

from typing import Any

from app.schemas.chat import ChatMessageItem
from app.utils.common import omit_fields
from app.utils.token import TokenCalculator


def _message_dict_for_token_count(msg: ChatMessageItem) -> dict[str, Any]:
    """将 ChatMessageItem 转为 count_message_tokens 所需的 dict。"""
    d = msg.model_dump(mode="json")
    return omit_fields(d, ["content", "reasoning", "reasoning_content"])


def count_chat_message_tokens(msg: ChatMessageItem, calculator: TokenCalculator) -> int:
    """单条 ChatMessageItem 的 token 数（基于 content_blocks 与 tool_calls）。"""
    return calculator.count_message_tokens(_message_dict_for_token_count(msg))


def split_history_by_rounds_and_tokens(
    messages: list[ChatMessageItem],
    max_rounds: int,
    max_tokens: int,
    token_calculator: TokenCalculator,
) -> tuple[list[ChatMessageItem], list[ChatMessageItem]]:
    """
    先按轮数保留最近 N 轮，再在 token 预算内从新到旧按「整轮」划分窗口内外消息。

    - 轮定义：一条 user + 一条 assistant（含其中 content_blocks 内的工具轨迹）为一轮。
    - token 截断时按整轮取舍，不拆开单轮，保证保留的 history 中 user/assistant 成对。
    - 假定 messages 按时间顺序 [旧, ..., 新]。
    - 返回 (窗口外的更早消息, 窗口内消息)。

    Args:
        messages: 按 message_ids 顺序的历史消息（通常为从旧到新）
        max_rounds: 最多保留轮数
        max_tokens: 历史 token 预算
        token_calculator: 用于计数的 TokenCalculator

    Returns:
        (out_of_window_messages, in_window_messages) 均为按时间正序
    """
    if not messages:
        return ([], [])

    if max_rounds <= 0 or max_tokens <= 0:
        return (messages, [])

    # 按轮分组：每轮 = 连续的一条 user + 一条 assistant
    rounds: list[list[ChatMessageItem]] = []
    i = 0
    while i < len(messages):
        if (
            i + 1 < len(messages)
            and messages[i].role == "user"
            and messages[i + 1].role == "assistant"
        ):
            rounds.append([messages[i], messages[i + 1]])
            i += 2
        else:
            i += 1

    # 只保留最近 max_rounds 轮
    rounds = rounds[-max_rounds:] if len(rounds) > max_rounds else rounds

    if not rounds:
        return ([], messages)

    # 在 token 预算内按「整轮」从新到旧累加，保证 user/assistant 成对
    tokens_used = 0
    kept_rounds: list[list[ChatMessageItem]] = []
    for round_messages in reversed(rounds):
        round_tokens = sum(
            count_chat_message_tokens(message, token_calculator)
            for message in round_messages
        )
        if kept_rounds and tokens_used + round_tokens > max_tokens:
            break
        tokens_used += round_tokens
        kept_rounds.append(round_messages)

    kept_rounds.reverse()
    kept = [message for round_messages in kept_rounds for message in round_messages]
    kept_ids = {message.id for message in kept}

    out_of_window_messages = [
        message for message in messages if message.id not in kept_ids
    ]
    in_window_messages = [
        message for message in messages if message.id in kept_ids]

    return (out_of_window_messages, in_window_messages)
