"""Chat 领域异常。"""

from __future__ import annotations


class ChatStreamError(Exception):
    """主会话流式生成失败。

    ``stream_turn_events`` 在已向客户端下发 error 事件后抛出，用于通知
    ``run_chat_turn`` 走失败收尾路径（标记消息 FAILED、trace 标 ERROR、跳过
    done 与记忆写入），而非误判为成功。
    """
