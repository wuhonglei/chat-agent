"""Agents module for chat service"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.base import BaseAgent
from app.agents.title_generation_agent import TitleGenerationAgent

if TYPE_CHECKING:
    from app.agents.chat_session_agent import ChatSessionAgent as ChatSessionAgent

__all__ = [
    "BaseAgent",
    "ChatSessionAgent",
    "TitleGenerationAgent",
]


def __getattr__(name: str) -> Any:
    if name == "ChatSessionAgent":
        from app.agents.chat_session_agent import ChatSessionAgent

        return ChatSessionAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
