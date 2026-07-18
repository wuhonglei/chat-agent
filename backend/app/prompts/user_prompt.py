"""用户消息提示词模板模块"""

from jinja2 import Template

# 共用的用户查询 XML（变量名统一为 user_message_text；可选 kb_context_blocks）
_USER_MESSAGE_QUERY_SNIPPET = """
<user_message>
  <query>{{ user_message_text|e }}</query>
  {%- if kb_context_blocks %}
  <attachment_context>
  {%- for attachment in kb_context_blocks %}
    <attachment index="{{ loop.index }}">
      <name>{{ attachment.name|e }}</name>
      {%- if attachment.created_at %}
      <created_at>{{ attachment.created_at|e }}</created_at>
      {%- endif %}
      <content>{{ attachment.content|e }}</content>
    </attachment>
  {%- endfor %}
  </attachment_context>
  {%- endif %}
  {%- if attachment_uploads %}
  <attachment_uploads note="以下为本会话已上传文件, markdown 为原始文件派生的可读 Markdown 文件">
  {%- for f in attachment_uploads %}
    <file index="{{ loop.index }}">
      <name>{{ f.name|e }}</name>
      <type>{{ f.type|e }}</type>
      <virtual_path>{{ f.virtual_path|e }}</virtual_path>
      <size>{{ f.human_size }}</size>
      {%- if f.token_size is not none %}
      <token_size>{{ f.token_size }}</token_size>
      {%- endif %}
      {%- if f.lines_count is not none %}
      <lines_count>{{ f.lines_count }}</lines_count>
      {%- endif %}
      <uploaded_this_turn>{{ 'true' if f.is_current_turn else 'false' }}</uploaded_this_turn>
      {%- if f.markdown %}
      <markdown>
        <name>{{ f.markdown.name|e }}</name>
        <virtual_path>{{ f.markdown.virtual_path|e }}</virtual_path>
        <size>{{ f.markdown.human_size }}</size>
        {%- if f.markdown.token_size is not none %}
        <token_size>{{ f.markdown.token_size }}</token_size>
        {%- endif %}
        {%- if f.markdown.lines_count is not none %}
        <lines_count>{{ f.markdown.lines_count }}</lines_count>
        {%- endif %}
      </markdown>
      {%- endif %}
    </file>
  {%- endfor %}
  </attachment_uploads>
  {%- endif %}
</user_message>
""".strip()

user_message_for_default_template: Template = Template(_USER_MESSAGE_QUERY_SNIPPET)

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<tool_call_context>
{%- if window_out_summary %}
  <window_out_summary>{{ window_out_summary|e }}</window_out_summary>
{%- endif %}
  {%- if user_memories %}
  <user_memories>
  {%- for memory in user_memories %}
    <memory_item>
      <memory>{{ memory.memory|e }}</memory>
      {%- if memory.created_at %}
      <created_at>{{ memory.created_at|e }}</created_at>
      {%- endif %}
      <relevance>{{ memory.relevance|e }}</relevance>
    </memory_item>
  {%- endfor %}
  </user_memories>
  {%- endif %}
  <current_datetime>{{ current_datetime|e }}</current_datetime>
</tool_call_context>
""".strip()
)

user_message_for_reach_tool_call_limit_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<tool_call_limit_notice>
  【系统说明】工具调用已达上限，请仅根据已有对话与工具结果直接作答；信息不足时请说明并给出力所能及的建议，勿再提议调用工具。
</tool_call_limit_notice>
""".strip()
)

user_message_for_no_tool_call_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<no_tool_call_notice>
  【系统说明】没有可用的工具，请直接给出最终回答。
</no_tool_call_notice>
""".strip()
)

gentle_tips_in_web_search_template: Template = Template(
    """
已调用 tavily_web_search，返回内容已包含相关片段，无需再调 tavily_web_pages_extract（除非需要完整网页内容）。
""".strip()
)

tool_call_sufficient_info_template: Template = Template(
    """
⚠️ 搜索结果可能已足够回答问题。请检查已调用工具及其结果，足够则直接给出最终回答，停止调用更多工具。
""".strip()
)

# ============= 上下文摘要相关提示词 =============
WINDOW_OUT_SUMMARY_MERGE_PROMPT: Template = Template(
    """
<task>
{%- if prior_summary %}
请将已有摘要与新增对话内容合并为一段简短摘要。
{%- else %}
请根据新增对话内容生成一段简短摘要。
{%- endif %}
</task>

<requirements>
{%- if prior_summary %}
<requirement>保留已有摘要的关键信息，并融入新增对话的要点，不要编造。</requirement>
{%- else %}
<requirement>只归纳新增对话中的关键信息，不要编造。</requirement>
{%- endif %}
<requirement>用自然语言、控制在 {{ max_tokens_hint }} 字以内。</requirement>
<requirement>若内容为空或无关紧要，可回复「无」。</requirement>
</requirements>

{%- if prior_summary %}
<prior_summary>
{{ prior_summary }}
</prior_summary>
{%- endif %}

<new_messages>
{{ new_messages_text }}
</new_messages>
""".strip()
)
