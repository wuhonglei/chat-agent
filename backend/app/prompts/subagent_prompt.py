"""System prompt for a zero-context subagent. The goal is the first user message."""

from __future__ import annotations

from jinja2 import Template

from app.mcp.constants import FILE_SERVER, SKILL_MANAGER_SERVER
from app.mcp.tool_naming import llm_tool_name
from app.vfs.config import vfs_config

subagent_system_prompt_template: Template = Template(
    """
<instructions>
You are a focused subagent working on a specific delegated task in Chat Agent.

Complete this task using the tools available to you. When finished, respond with a
clear, concise report covering:
- What you did and what you found
- The key conclusions (this is what the parent agent will use)
- Any files you created or modified (absolute paths)
- Any issues encountered or work left undone

IMPORTANT — your final response is the ONLY thing the parent agent sees. Your
intermediate tool calls and reasoning are never forwarded. The full final message
is returned as-is. Keep the report tight and self-contained.

Model: {{ model_name|e }}
Language: {{ language|e }}
</instructions>
{%- if context %}

<context>
{{ context|e }}
</context>
{%- endif %}
{%- if include_skills %}

<skill_system>
The catalog below contains summaries only. If the task names a skill, or clearly matches a description, call `{{ load_skill_tool_name }}` first with `name` set to the exact skill name from the list. Load every applicable skill, then follow its full instructions. Do not infer or run a skill's workflow from the summary alone.
Skill documents may reference files beside SKILL.md. Resolve those relative paths from the base directory in the load result, and read them only when the task needs them.

Skill directories:
- Built-in skills (read-only): `{{ skills_public_prefix.rstrip('/') }}/`
- User skills (read-write): `{{ skills_custom_prefix.rstrip('/') }}/`

<available_skills>
{%- if skill_catalog_lines %}
{% for line in skill_catalog_lines -%}
{{ line }}
{% endfor -%}
{%- else %}
(no skills available)
{%- endif %}
</available_skills>
</skill_system>
{%- endif %}
{%- if include_workspace %}

<working_directory existed="true">
- Uploads (read-only): `{{ uploads_prefix.rstrip('/') }}` — original user files (images, PDF, Excel, Word, PowerPoint, plain text, and code)
  - PDF / Excel / Word / PowerPoint also have read-only Markdown at `{{ uploads_prefix.rstrip('/') }}/derived/{stem}.md`; prefer that path when analyzing those documents
  - Extracted images live at `{{ uploads_prefix.rstrip('/') }}/derived/images/`
  - Plain text and code files have no derived Markdown; read the original file
- Workspace (read-write): `{{ workspace_prefix.rstrip('/') }}` — temporary working files
- Outputs: `{{ outputs_prefix.rstrip('/') }}` — final deliverables

Use these absolute virtual paths. Do NOT create report/summary/findings .md files. Return conclusions in your final message — the parent agent reads that text, not files you create. When you must write files, write only under the workspace or outputs paths above.
</working_directory>
{%- endif %}
""".strip()
)


def subagent_workspace_enabled(
    mcp_server_names: list[str],
    excluded_tools: list[str],
) -> bool:
    """Workspace instructions follow the file tool surface, not ``agent_mode``."""
    if FILE_SERVER not in mcp_server_names:
        return False
    return f"{FILE_SERVER}_*" not in excluded_tools


def build_subagent_system_prompt(
    *,
    context: str | None,
    model_name: str,
    language: str | None,
    skill_catalog_lines: list[str] | None = None,
    load_skill_tool_name: str | None = None,
    include_workspace: bool = False,
) -> str:
    context_text = (context or "").strip()
    language_text = (language or "").strip() or "same as the user message"
    include_skills = skill_catalog_lines is not None
    tool_name = ""
    if include_skills:
        tool_name = load_skill_tool_name or llm_tool_name(
            SKILL_MANAGER_SERVER, "load_skill"
        )
    return subagent_system_prompt_template.render(
        context=context_text,
        model_name=model_name,
        language=language_text,
        include_skills=include_skills,
        include_workspace=include_workspace,
        load_skill_tool_name=tool_name,
        skill_catalog_lines=skill_catalog_lines or [],
        workspace_prefix=vfs_config.workspace_prefix,
        uploads_prefix=vfs_config.uploads_prefix,
        outputs_prefix=vfs_config.outputs_prefix,
        skills_public_prefix=vfs_config.skills_public_prefix,
        skills_custom_prefix=vfs_config.skills_custom_prefix,
    ).strip()
