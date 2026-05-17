"""提示词工具函数模块"""

from __future__ import annotations

import platform
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

from app.agent_skills.models import AgentSkillManifest
from app.agent_skills.registry import SKILLS_DIR
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_chat_session_template,
    system_prompt_for_title_template,
)
from app.prompts.user_prompt import (
    WINDOW_OUT_SUMMARY_MERGE_PROMPT,
    disabled_tools_message_template,
    gentle_tips_in_web_search_template,
    tool_call_sufficient_info_template,
    user_message_for_default_template,
    user_message_for_no_tool_call_template,
    user_message_for_reach_tool_call_limit_template,
    user_message_for_tool_call_template,
)
from app.schemas.chat import ContentBlock, KbContextBlock
from app.schemas.user import MemorySearchItem
from app.utils.date import get_current_datetime_str


def _get_command_version(command: list[str]) -> str:
    """Get command version output safely."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"

    output = (result.stdout or result.stderr).strip()
    if not output:
        return "unknown"
    return output.splitlines()[0]


def _get_runtime_environment(user_id: str, workspace_id: str) -> dict[str, str]:
    """Get runtime environment summary for prompts."""
    safe_workspace_id = workspace_id.strip()
    workspace_dir = f"data/user_data/{user_id}/workspaces/{safe_workspace_id}"
    return {
        "system_type": (
            f"{platform.system()} {platform.release()} ({platform.machine()})"
        ),
        "node_version": _get_command_version(["node", "--version"]),
        "python_version": sys.version.split()[0],
        "skills_dir": str(SKILLS_DIR),
        "workspace_dir": str(workspace_dir),
    }


def get_default_system_prompt() -> str:
    """Get default system prompt with current time information"""
    return default_system_prompt_template.render()


def get_system_prompt_for_chat_session(
    *,
    website_build_mode: bool = False,
    skill_manifests: Sequence[AgentSkillManifest] | None = None,
    user_id: str,
    workspace_id: str,
) -> str:
    """Get system prompt for final response generation."""
    runtime_environment = _get_runtime_environment(user_id, workspace_id)
    # 统一单会话 Agent 的 system：最终回答优先 + 工具调用准则（balanced）。
    return system_prompt_for_chat_session_template.render(
        website_build_mode=website_build_mode,
        skill_manifests=skill_manifests or [],
        **runtime_environment,
    )


def get_system_prompt_for_title() -> str:
    """Get system prompt for title generation"""
    return system_prompt_for_title_template.render().strip()


def get_user_message_for_tool_calls(
    user_message_text: str,
    kb_context_blocks: list[KbContextBlock] | None = None,
    user_memories: Sequence[MemorySearchItem] | None = None,
    window_out_summary: str | None = None,
) -> str:
    """Get user message prompt for tool calls.

    kb_context_blocks: 可选，每项建议包含 id、name、content，
    以及可选 created_at（与 user_prompt 模板一致）。
    """
    return user_message_for_tool_call_template.render(
        user_message_text=user_message_text,
        kb_context_blocks=kb_context_blocks or [],
        user_memories=user_memories,
        window_out_summary=window_out_summary,
        current_datetime=get_current_datetime_str(),
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


def get_disabled_tools_message(disabled_tools: list[str]) -> str:
    """Get disabled tools message"""
    return disabled_tools_message_template.render(disabled_tools=disabled_tools).strip()


def get_gentle_tips_in_web_search() -> str:
    """Get gentle tips in web search"""
    return gentle_tips_in_web_search_template.render().strip()


def get_tool_call_sufficient_info_message() -> str:
    """Get message when sufficient info may have been obtained"""
    return tool_call_sufficient_info_template.render().strip()


def get_user_message_for_reach_tool_call_limit(
    user_message: str,
    kb_context_blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message for reach tool call limit"""
    return user_message_for_reach_tool_call_limit_template.render(
        user_message_text=user_message,
        kb_context_blocks=kb_context_blocks or [],
    ).strip()


def get_user_message_for_no_tool_call(
    user_message: str,
    kb_context_blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message for no tool call"""
    return user_message_for_no_tool_call_template.render(
        user_message_text=user_message,
        kb_context_blocks=kb_context_blocks or [],
    ).strip()
