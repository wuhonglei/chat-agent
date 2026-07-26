"""上下文摘要服务：窗口外消息摘要"""

from __future__ import annotations

from app.prompts.prompt_utils import (
    get_window_out_summary_compress_prompt,
    get_window_out_summary_merge_prompt,
)
from app.schemas.chat import (
    ChatMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.services.base_service.llm_service import LLMService
from app.services.base_service.model_resolver import resolve_scenario
from app.utils.logger import logger

# 与 opencode compaction 一致：摘要输入中的工具输出截断，避免撑爆 summarizer
_SUMMARY_TOOL_RESULT_MAX_CHARS = 2000
_SUMMARY_TOOL_ARG_MAX_CHARS = 500


class ContextSummaryService(LLMService):
    """窗口外消息摘要（调用 LLM，继承 LLMService 统一 API 调用）"""

    def __init__(self) -> None:
        llm_config = resolve_scenario("summarization")
        super().__init__(llm_config, think_mode=False)

    def format_conversation_for_summary(
        self,
        messages: list[ChatMessage],
    ) -> str:
        """将消息列表拼接为一段文本供 LLM 阅读（含工具调用与截断后的结果）。"""
        parts: list[str] = []
        for m in messages:
            for block in m.content_blocks:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if text:
                        parts.append(f"[{m.role}]: {text}")
                elif isinstance(block, ToolUseBlock):
                    name = block.name or "unknown_tool"
                    args = (block.arguments_text or "").strip()
                    if len(args) > _SUMMARY_TOOL_ARG_MAX_CHARS:
                        args = (
                            args[:_SUMMARY_TOOL_ARG_MAX_CHARS]
                            + f"... [{len(block.arguments_text or '')} chars]"
                        )
                    parts.append(f"[assistant tool_call]: {name}({args})")
                elif isinstance(block, ToolResultBlock):
                    content = (block.summary or block.content or "").strip()
                    if len(content) > _SUMMARY_TOOL_RESULT_MAX_CHARS:
                        content = (
                            content[:_SUMMARY_TOOL_RESULT_MAX_CHARS] + "\n[truncated]"
                        )
                    if not content:
                        continue
                    label = "tool_result_error" if block.is_error else "tool_result"
                    parts.append(f"[{label}]: {content}")
        return "\n\n".join(parts)

    async def _compress_summary(self, prior_summary: str, max_tokens: int) -> str:
        """摘要自压缩：prior_summary 过大时压到目标规模。"""
        prompt = get_window_out_summary_compress_prompt(
            prior_summary=prior_summary,
            max_tokens=max_tokens,
        )
        try:
            resp = await self.call_llm_api(
                self.model_name,
                [{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=max_tokens,
                extra_body=self.extra_body,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content[: max_tokens * 2]
        except Exception as e:
            logger.warning("Summary self-compress LLM call failed", error=e)
        return self.token_calculator.truncate_text_to_tokens(
            prior_summary, max_tokens=max_tokens
        )

    async def summarize_merge(
        self,
        prior_summary: str | None,
        messages_to_summarize: list[ChatMessage],
        max_tokens: int,
    ) -> str:
        """生成或增量合并窗口外摘要。"""
        normalized_prior_summary = prior_summary.strip() if prior_summary else ""
        if not messages_to_summarize:
            return normalized_prior_summary[: max_tokens * 2]
        new_text = self.format_conversation_for_summary(messages_to_summarize)
        if not new_text.strip():
            return normalized_prior_summary[: max_tokens * 2]

        if normalized_prior_summary:
            prior_tokens = self.token_calculator.count_tokens(normalized_prior_summary)
            if prior_tokens > max_tokens * 1.5:
                normalized_prior_summary = await self._compress_summary(
                    normalized_prior_summary, max_tokens // 2
                )

        max_source_tokens = int(
            self.model_limit * (0.8 if normalized_prior_summary else 0.5)
        )
        new_truncated = self.token_calculator.truncate_text_to_tokens(
            new_text, max_tokens=max_source_tokens
        )
        prompt = get_window_out_summary_merge_prompt(
            prior_summary=normalized_prior_summary,
            new_messages_text=new_truncated,
            max_tokens=max_tokens,
        )
        try:
            resp = await self.call_llm_api(
                self.model_name,
                [{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=max_tokens,
                extra_body=self.extra_body,
            )
            content = (resp.choices[0].message.content or "").strip()
            return content[: max_tokens * 2]
        except Exception as e:
            logger.warning(
                "Window-out merge summary LLM call failed",
                error=e,
                message_count=len(messages_to_summarize),
            )
            raise
