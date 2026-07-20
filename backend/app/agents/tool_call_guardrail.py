"""Request-scoped tool-call circuit breaker (hermes-style)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.mcp.constants import (
    FILE_SERVER,
    IDEMPOTENT_LLM_TOOLS,
    MUTATING_LLM_TOOLS,
    SHELL_SERVER,
)


class GuardrailDecisionKind(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    HALT = "halt"


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    kind: GuardrailDecisionKind
    message: str = ""


@dataclass
class ToolCallGuardrail:
    """Track exact / same-tool failures and idempotent no-progress loops."""

    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    no_progress_warn_after: int = 3
    no_progress_block_after: int = 5

    halted: bool = False
    _exact_failure_counts: dict[str, int] = field(default_factory=dict)
    _same_tool_failure_counts: dict[str, int] = field(default_factory=dict)
    _no_progress: dict[str, tuple[str, int]] = field(default_factory=dict)
    _no_progress_blocked: set[str] = field(default_factory=set)

    def reset(self) -> None:
        self.halted = False
        self._exact_failure_counts.clear()
        self._same_tool_failure_counts.clear()
        self._no_progress.clear()
        self._no_progress_blocked.clear()

    @staticmethod
    def call_signature(tool_name: str, arguments: dict[str, Any]) -> str:
        canonical = json.dumps(
            arguments, sort_keys=True, ensure_ascii=False, default=str
        )
        digest = hashlib.sha256(f"{tool_name}:{canonical}".encode()).hexdigest()
        return digest

    @staticmethod
    def result_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def is_idempotent(tool_name: str) -> bool:
        if tool_name in MUTATING_LLM_TOOLS:
            return False
        return tool_name in IDEMPOTENT_LLM_TOOLS

    def before_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> GuardrailDecision:
        if self.halted:
            return GuardrailDecision(
                kind=GuardrailDecisionKind.HALT,
                message=self._halt_message(tool_name, skipped=True),
            )

        signature = self.call_signature(tool_name, arguments)
        exact_count = self._exact_failure_counts.get(signature, 0)
        if exact_count >= self.exact_failure_block_after:
            return GuardrailDecision(
                kind=GuardrailDecisionKind.BLOCK,
                message=(
                    f"已阻断 {tool_name}：相同参数连续失败 "
                    f"{exact_count} 次。请更换参数或换用其他工具，"
                    "不要原样重试。"
                ),
            )

        same_count = self._same_tool_failure_counts.get(tool_name, 0)
        if same_count >= self.same_tool_failure_halt_after:
            self.halted = True
            return GuardrailDecision(
                kind=GuardrailDecisionKind.HALT,
                message=self._halt_message(tool_name, failure_count=same_count),
            )

        if signature in self._no_progress_blocked:
            return GuardrailDecision(
                kind=GuardrailDecisionKind.BLOCK,
                message=(
                    f"已阻断 {tool_name}：相同参数连续返回完全相同的结果 "
                    f"{self.no_progress_block_after} 次，无明显进展。"
                    "请更换查询/路径或换用其他工具。"
                ),
            )

        return GuardrailDecision(kind=GuardrailDecisionKind.ALLOW)

    def record_outcome(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        content: str,
    ) -> str:
        """Update counters after a real tool call. Returns warning suffix (may be empty)."""
        signature = self.call_signature(tool_name, arguments)
        if success:
            self._exact_failure_counts.pop(signature, None)
            self._same_tool_failure_counts.pop(tool_name, None)
            return self._record_no_progress(tool_name, signature, content)

        exact_count = self._exact_failure_counts.get(signature, 0) + 1
        same_count = self._same_tool_failure_counts.get(tool_name, 0) + 1
        self._exact_failure_counts[signature] = exact_count
        self._same_tool_failure_counts[tool_name] = same_count
        self._no_progress.pop(signature, None)

        warnings: list[str] = []
        if exact_count >= self.exact_failure_warn_after:
            warnings.append(
                f"⚠️ 警告：{tool_name} 使用相同参数已连续失败 {exact_count} 次。"
                "请更换策略（改参数、换路径或换工具），避免原样重试。"
            )
        if same_count >= self.same_tool_failure_warn_after:
            warnings.append(
                f"⚠️ 警告：工具 {tool_name} 已连续失败 {same_count} 次。"
                f"{self._recovery_hint(tool_name)}"
            )
        if same_count >= self.same_tool_failure_halt_after:
            self.halted = True
            warnings.append(self._halt_message(tool_name, failure_count=same_count))

        if not warnings:
            return ""
        return "\n\n" + "\n".join(warnings)

    def _record_no_progress(self, tool_name: str, signature: str, content: str) -> str:
        if not self.is_idempotent(tool_name):
            return ""

        current_hash = self.result_hash(content)
        previous = self._no_progress.get(signature)
        if previous is not None and previous[0] == current_hash:
            repeat_count = previous[1] + 1
        else:
            repeat_count = 1
        self._no_progress[signature] = (current_hash, repeat_count)

        if repeat_count >= self.no_progress_block_after:
            self._no_progress_blocked.add(signature)

        if repeat_count >= self.no_progress_warn_after:
            return (
                f"\n\n⚠️ 警告：{tool_name} 使用相同参数已连续 "
                f"{repeat_count} 次返回相同结果，可能没有进展。"
                "请更换查询条件或换用其他工具。"
            )
        return ""

    def synthetic_halt_message(self, tool_name: str) -> str:
        return self._halt_message(tool_name, skipped=True)

    def _halt_message(
        self,
        tool_name: str,
        *,
        failure_count: int | None = None,
        skipped: bool = False,
    ) -> str:
        count_part = (
            f"已连续失败 {failure_count} 次。"
            if failure_count is not None
            else "本轮工具调用已被熔断。"
        )
        skipped_part = "本次调用未执行。" if skipped else ""
        return (
            f"🛑 熔断：{tool_name} {count_part}{skipped_part}"
            "请停止继续调用工具，直接根据已有信息给出最终回答。"
            f"{self._recovery_hint(tool_name)}"
        )

    @staticmethod
    def _recovery_hint(tool_name: str) -> str:
        if tool_name.startswith(f"{SHELL_SERVER}_"):
            return (
                " 对于 shell 失败，可先运行简单诊断（如 pwd && ls -la），"
                "改用绝对路径/更简单命令，或改用 file_read_file / file_write_file。"
            )
        if tool_name.startswith(f"{FILE_SERVER}_"):
            return (
                " 对于文件工具失败，请确认路径位于 /mnt/user-data/ 下，"
                "并检查文件是否存在、是否有写权限。"
            )
        return " 请更换参数或换用其他工具，停止重复失败的调用。"
