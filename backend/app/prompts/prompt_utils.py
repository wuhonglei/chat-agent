"""提示词工具函数模块"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.agent_skills.render import format_catalog_entries
from app.agent_skills.types import AgentSkillManifest
from app.mcp.constants import PRESENT_FILES_LLM, SKILL_MANAGER_SERVER
from app.mcp.tool_naming import llm_tool_name
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_chat_session_template,
    system_prompt_for_title_template,
)
from app.prompts.user_prompt import (
    WINDOW_OUT_SUMMARY_COMPRESS_PROMPT,
    WINDOW_OUT_SUMMARY_MERGE_PROMPT,
    gentle_tips_in_web_search_template,
    tool_call_sufficient_info_template,
    user_message_for_continue_task_template,
    user_message_for_default_template,
    user_message_for_no_tool_call_template,
    user_message_for_reach_tool_call_limit_template,
    user_message_for_summarize_task_template,
    user_message_for_tool_call_template,
)
from app.schemas.chat import AttachmentUploadInfo, ContentBlock, KbContextBlock
from app.schemas.user import MemorySearchItem
from app.utils.date import get_current_datetime_str
from app.vfs.config import vfs_config


def _get_agent_mode_prompt_context() -> dict[str, str]:
    """VFS path prefixes injected into system prompt when agent_mode > 0."""
    return {
        "workspace_prefix": vfs_config.workspace_prefix,
        "outputs_prefix": vfs_config.outputs_prefix,
        "uploads_prefix": vfs_config.uploads_prefix,
        "skills_public_prefix": vfs_config.skills_public_prefix,
        "skills_custom_prefix": vfs_config.skills_custom_prefix,
    }


def get_default_system_prompt() -> str:
    """Get default system prompt with current time information"""
    return default_system_prompt_template.render()


def get_system_prompt_for_chat_session(
    *,
    agent_mode: int = 0,
    skill_manifests: Sequence[AgentSkillManifest] | None = None,
    window_out_summary: str | None = None,
) -> str:
    """Get system prompt for chat session, optionally with window-out summary."""
    manifests = list(skill_manifests or [])
    extra: dict[str, Any] = (
        dict(_get_agent_mode_prompt_context()) if agent_mode > 0 else {}
    )
    if agent_mode > 0:
        extra["load_skill_tool_name"] = llm_tool_name(
            SKILL_MANAGER_SERVER, "load_skill"
        )
        extra["present_files_tool_name"] = PRESENT_FILES_LLM
        extra["skill_catalog_lines"] = format_catalog_entries(manifests)
    summary = (window_out_summary or "").strip() or None
    return system_prompt_for_chat_session_template.render(
        agent_mode=agent_mode,
        skill_manifests=manifests,
        window_out_summary=summary,
        **extra,
    )


def get_system_prompt_for_title() -> str:
    """Get system prompt for title generation"""
    return system_prompt_for_title_template.render().strip()


def get_user_message_for_tool_calls(
    user_message_text: str,
    kb_context_blocks: list[KbContextBlock] | None = None,
    user_memories: Sequence[MemorySearchItem] | None = None,
    attachment_uploads: list[AttachmentUploadInfo] | None = None,
    current_datetime: str | None = None,
) -> str:
    """Get user message prompt for tool calls.

    kb_context_blocks: 可选，每项建议包含 name、content，
    以及可选 created_at（与 user_prompt 模板一致）。
    attachment_uploads: 可选，agent_mode 下注入的上传文件清单，
    由模型用文件工具按需读取。
    current_datetime: 可选，turn 级冻结的时间字符串（通常为 user 消息
        created_at）；缺省才实时取。
    """
    return user_message_for_tool_call_template.render(
        user_message_text=user_message_text,
        kb_context_blocks=kb_context_blocks or [],
        user_memories=user_memories,
        attachment_uploads=attachment_uploads or [],
        current_datetime=current_datetime or get_current_datetime_str(),
    ).strip()


def get_user_message_for_title(
    user_message_text: str,
    kb_context_blocks: list[KbContextBlock] | None = None,
) -> str:
    """Get user message prompt for title generation.

    仅使用至多 1 条附件（取列表首项，调用方宜传入已按相关性排序的 top-k）。
    """
    return user_message_for_default_template.render(
        user_message_text=user_message_text,
        kb_context_blocks=(kb_context_blocks or [])[:1],
    ).strip()


def get_window_out_summary_merge_prompt(
    prior_summary: str,
    new_messages_text: str,
    max_tokens: int,
) -> str:
    """渲染窗口外合并摘要的 prompt（已有摘要 + 新增消息内容 → 合并摘要）。"""
    return WINDOW_OUT_SUMMARY_MERGE_PROMPT.render(
        prior_summary=prior_summary,
        new_messages_text=new_messages_text,
        max_tokens_hint=max_tokens,
    ).strip()


def get_window_out_summary_compress_prompt(
    prior_summary: str,
    max_tokens: int,
) -> str:
    """渲染摘要自压缩 prompt。"""
    return WINDOW_OUT_SUMMARY_COMPRESS_PROMPT.render(
        prior_summary=prior_summary,
        max_tokens_hint=max_tokens,
    ).strip()


def get_prompt_for_title(
    user_input: str | list[ContentBlock] | list[dict[str, Any]],
    kb_context_blocks: list[KbContextBlock] | None = None,
) -> tuple[str, str | list[dict[str, Any]]]:
    """Get combined system prompt and user message for title generation.

    Pass a string for text-only, or content blocks to include images in the user message.
    """
    from app.utils.multimodal import build_title_user_message_for_llm

    system_prompt = get_system_prompt_for_title().strip()
    if isinstance(user_input, str):
        return system_prompt, get_user_message_for_title(user_input, kb_context_blocks)
    user_message_prompt = build_title_user_message_for_llm(
        user_input, kb_context_blocks
    )
    return system_prompt, user_message_prompt


def get_gentle_tips_in_web_search() -> str:
    """Get gentle tips in web search"""
    return gentle_tips_in_web_search_template.render().strip()


def get_tool_call_sufficient_info_message() -> str:
    """Get message when sufficient info may have been obtained"""
    return tool_call_sufficient_info_template.render().strip()


def get_iteration_checkpoint_notice(*, iterations_used: int) -> str:
    """Agent 模式触达轮次上限后的检查点 trailing notice（不含原始 query）。"""
    return user_message_for_reach_tool_call_limit_template.render(
        iterations_used=iterations_used,
    ).strip()


def get_continue_task_notice(*, continue_budget: int) -> str:
    """用户确认续跑后的 trailing notice。"""
    return user_message_for_continue_task_template.render(
        continue_budget=continue_budget,
    ).strip()


def get_summarize_task_notice() -> str:
    """用户选择到此为止后的 trailing notice。"""
    return user_message_for_summarize_task_template.render().strip()


def get_user_message_for_reach_tool_call_limit(
    user_message: str,
    kb_context_blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Deprecated: 保留兼容导出；请改用 get_iteration_checkpoint_notice。"""
    _ = user_message, kb_context_blocks
    return get_iteration_checkpoint_notice(iterations_used=0)


def get_user_message_for_no_tool_call(
    user_message: str,
    kb_context_blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message for no tool call"""
    return user_message_for_no_tool_call_template.render(
        user_message_text=user_message,
        kb_context_blocks=kb_context_blocks or [],
    ).strip()
