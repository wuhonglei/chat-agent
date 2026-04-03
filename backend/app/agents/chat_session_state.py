"""State helpers for chat session execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.schemas.chat import ContentBlock
from app.schemas.llm import ToolMessage


class ChatRoundStage(str, Enum):
    # 正在流式生成本轮模型输出（可能产出文本/思考/工具调用增量）。
    GENERATING = "generating"
    # 已识别到工具调用，进入工具执行阶段。
    TOOL_CALLING = "tool_calling"
    # 工具执行完成，正在回填工具结果并整理本轮输出。
    FINALIZING = "finalizing"
    # 本轮处理结束（无工具调用直接结束，或工具链路完成后结束）。
    DONE = "done"


@dataclass
class SessionAggregate:
    """All mutable chat session output in one place."""

    output_messages: list[ToolMessage] = field(default_factory=list)
    content_blocks: list[ContentBlock] = field(default_factory=list)
    content: str = ""
    reasoning: str = ""

    def reset(self) -> None:
        self.output_messages.clear()
        self.content_blocks = []
        self.content = ""
        self.reasoning = ""


@dataclass
class RoundExecution:
    """Per-round execution status."""

    stage: ChatRoundStage = ChatRoundStage.GENERATING
    final_answer_done: bool = False


class ChatRoundStateMachine:
    """Explicit state transitions for one model/tool round."""

    def __init__(self) -> None:
        self.current = RoundExecution()

    def start_round(self) -> RoundExecution:
        self.current = RoundExecution(stage=ChatRoundStage.GENERATING)
        return self.current

    def begin_tool_calling(self) -> None:
        self.current.stage = ChatRoundStage.TOOL_CALLING

    def begin_finalizing(self) -> None:
        self.current.stage = ChatRoundStage.FINALIZING

    def mark_done(self) -> None:
        self.current.stage = ChatRoundStage.DONE
        self.current.final_answer_done = True
