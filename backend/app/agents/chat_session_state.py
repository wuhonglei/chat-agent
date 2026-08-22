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
class SessionOutput:
    """All mutable chat session output in one place."""

    tool_round_messages: list[ToolMessage] = field(default_factory=list)
    content_blocks: list[ContentBlock] = field(default_factory=list)
    content: str = ""
    reasoning: str = ""
    # Agent 模式触达轮次上限后的检查点；落库 / done SSE 用
    iteration_checkpoint: dict[str, int] | None = None

    def reset(self) -> None:
        self.tool_round_messages.clear()
        self.content_blocks = []
        self.content = ""
        self.reasoning = ""
        self.iteration_checkpoint = None


@dataclass
class RoundState:
    """Per-round execution status."""

    stage: ChatRoundStage = ChatRoundStage.GENERATING
    is_final_answer_complete: bool = False


class ChatRoundStateMachine:
    """Explicit state transitions for one model/tool round."""

    def __init__(self) -> None:
        self.current_round = RoundState()

    def start_round(self) -> RoundState:
        self.current_round = RoundState(stage=ChatRoundStage.GENERATING)
        return self.current_round

    def begin_tool_calling(self) -> None:
        self.current_round.stage = ChatRoundStage.TOOL_CALLING

    def begin_finalizing(self) -> None:
        self.current_round.stage = ChatRoundStage.FINALIZING

    def mark_done(self) -> None:
        self.current_round.stage = ChatRoundStage.DONE
        self.current_round.is_final_answer_complete = True
