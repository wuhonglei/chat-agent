"""历史消息按轮数与 token 截断"""

from app.schemas.chat import ChatMessage
from app.utils.token import TokenCalculator


def count_chat_message_tokens(msg: ChatMessage, calculator: TokenCalculator) -> int:
    """单条 ChatMessage 的 token 数（基于 content_blocks 与 tool_calls）。"""
    return calculator.count_message_tokens(msg.model_dump(mode="json"))


def group_history_into_user_assistant_rounds(
    messages: list[ChatMessage],
) -> list[list[ChatMessage]]:
    """将消息按「一条 user + 一条 assistant」划为轮次（时间正序）。"""
    rounds: list[list[ChatMessage]] = []
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
    return rounds


def split_history_by_rounds(
    messages: list[ChatMessage],
    max_rounds: int,
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    """
    仅按轮数保留最近 N 轮，划分窗口内外消息。

    - 轮定义：一条 user + 一条 assistant 为一轮。
    - 假定 messages 按时间顺序 [旧, ..., 新]。
    - 返回 (窗口外的更早消息, 窗口内消息)。

    Args:
        messages: 按 message_ids 顺序的历史消息（通常为从旧到新）
        max_rounds: 最多保留轮数；<=0 时全部视为窗口外

    Returns:
        (out_of_window_messages, in_window_messages) 均为按时间正序
    """
    if not messages:
        return ([], [])

    if max_rounds <= 0:
        return (messages, [])

    rounds = group_history_into_user_assistant_rounds(messages)
    if not rounds:
        return ([], messages)

    rounds = rounds[-max_rounds:] if len(rounds) > max_rounds else rounds
    kept = [message for round_messages in rounds for message in round_messages]
    kept_ids = {message.id for message in kept}

    out_of_window_messages = [
        message for message in messages if message.id not in kept_ids
    ]
    in_window_messages = [message for message in messages if message.id in kept_ids]

    return (out_of_window_messages, in_window_messages)


def truncate_in_window_by_round_tokens(
    messages: list[ChatMessage],
    max_tokens: int,
    token_calculator: TokenCalculator,
) -> list[ChatMessage]:
    """
    在已对工具结果等做过压缩后的窗口内消息上，按整轮、从新到旧在 token 预算内截断。

    - max_tokens <= 0 时返回空列表（窗口内不保留消息）。
    - 若无法组成任何完整轮次，则不做 token 截断，原样返回（与仅按轮筛选后的形状一致）。
    """
    if not messages:
        return []

    if max_tokens <= 0:
        return []

    rounds = group_history_into_user_assistant_rounds(messages)
    if not rounds:
        return list(messages)

    tokens_used = 0
    kept_rounds: list[list[ChatMessage]] = []
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
    return [message for round_messages in kept_rounds for message in round_messages]
