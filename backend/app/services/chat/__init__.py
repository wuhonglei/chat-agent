"""聊天领域服务。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.chat.chat_service import ChatService as ChatService

__all__ = ["ChatService"]


def __getattr__(name: str) -> Any:
    if name == "ChatService":
        from app.services.chat.chat_service import ChatService

        return ChatService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
