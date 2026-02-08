"""历史消息按轮数与 token 截断"""

from typing import Any

from app.schemas.chat import ChatMessageItem
from app.utils.common import omit_fields
from app.utils.token import TokenCalculator


def _message_dict_for_token_count(msg: ChatMessageItem) -> dict[str, Any]:
    """将 ChatMessageItem 转为 count_message_tokens 所需的 dict（不含 reasoning_content、tool_calls、component_tool_calls）。"""
    d = msg.model_dump(mode="json")
    return omit_fields(d, ["reasoning_content", "tool_calls", "component_tool_calls"])


def count_chat_message_tokens(msg: ChatMessageItem, calculator: TokenCalculator) -> int:
    """单条 ChatMessageItem 的 token 数（含 content、reasoning、tool_calls）。"""
    return calculator.count_message_tokens(_message_dict_for_token_count(msg))


def truncate_history_by_rounds_and_tokens(
    messages: list[ChatMessageItem],
    max_rounds: int,
    max_tokens: int,
    token_calculator: TokenCalculator,
) -> tuple[list[ChatMessageItem], list[ChatMessageItem]]:
    """
    先按轮数保留最近 N 轮，再在 token 预算内从新到旧按「整轮」保留消息。

    - 轮定义：一条 user + 一条 assistant（含其中 tool_calls）为一轮。
    - token 截断时按整轮取舍，不拆开单轮，保证保留的 history 中 user/assistant 成对。
    - 假定 messages 按时间顺序 [旧, ..., 新]。
    - 返回 (本次保留的 history_messages, 被截掉的更早消息)。

    Args:
        messages: 按 message_ids 顺序的历史消息（通常为从旧到新）
        max_rounds: 最多保留轮数
        max_tokens: 历史 token 预算
        token_calculator: 用于计数的 TokenCalculator

    Returns:
        (kept_messages, truncated_messages) 均为按时间正序
    """
    if not messages:
        return ([], [])

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

    # 只保留最近 max_rounds 轮
    rounds = rounds[-max_rounds:] if len(rounds) > max_rounds else rounds

    if not rounds:
        return ([], messages)

    # 在 token 预算内按「整轮」从新到旧累加，保证 user/assistant 成对
    tokens_used = 0
    kept_rounds: list[list[ChatMessageItem]] = []
    for r in reversed(rounds):
        round_tokens = sum(count_chat_message_tokens(m, token_calculator) for m in r)
        tokens_used += round_tokens
        kept_rounds.append(r)
        if tokens_used >= max_tokens:
            break

    kept_rounds.reverse()
    kept: list[ChatMessageItem] = []
    for r in kept_rounds:
        kept.extend(r)

    after_rounds: list[ChatMessageItem] = []
    for r in rounds:
        after_rounds.extend(r)
    kept_ids = {m.id for m in kept}
    truncated = [m for m in after_rounds if m.id not in kept_ids]

    return (kept, truncated)
