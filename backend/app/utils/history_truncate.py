"""历史消息按轮次与 token 预算切分"""

from app.protocols.chat_messages import format_chat_message_for_llm
from app.schemas.chat import ChatMessage
from app.utils.token import TokenCalculator


def count_chat_message_tokens(msg: ChatMessage, calculator: TokenCalculator) -> int:
    """单条 ChatMessage 的 token 数。

    user 消息优先按实际发给 LLM 的文本（含 llm_rendered_text 快照）计；
    assistant 仍基于 content_blocks dump（含工具块）。
    """
    if msg.role == "user":
        return calculator.count_message_tokens(format_chat_message_for_llm(msg))
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


def split_history_by_token_budget(
    messages: list[ChatMessage],
    max_tokens: int,
    token_calculator: TokenCalculator,
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    """按动态 token 预算从最新轮往旧累加，划分窗口内外。

    - 假定 messages 按时间顺序 [旧, ..., 新]。
    - 从最新轮往旧累加整轮 token，超出 max_tokens 的更早轮次为窗口外。
    - max_tokens <= 0 时全部视为窗口外。

    Returns:
        (in_window_messages, out_of_window_messages) 均为按时间正序
    """
    if not messages:
        return ([], [])

    if max_tokens <= 0:
        return ([], list(messages))

    rounds = group_history_into_user_assistant_rounds(messages)
    if not rounds:
        # 无法组成完整轮次时，整段按单条从新到旧塞入预算
        tokens_used = 0
        kept: list[ChatMessage] = []
        for message in reversed(messages):
            msg_tokens = count_chat_message_tokens(message, token_calculator)
            if kept and tokens_used + msg_tokens > max_tokens:
                break
            tokens_used += msg_tokens
            kept.append(message)
        kept.reverse()
        kept_ids = {m.id for m in kept}
        out_of_window = [m for m in messages if m.id not in kept_ids]
        return (kept, out_of_window)

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
    in_window = [
        message for round_messages in kept_rounds for message in round_messages
    ]
    kept_ids = {message.id for message in in_window}
    out_of_window = [message for message in messages if message.id not in kept_ids]
    return (in_window, out_of_window)
