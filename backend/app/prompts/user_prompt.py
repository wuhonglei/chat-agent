"""用户消息提示词模板模块"""

from jinja2 import Template

# 共用的用户查询 XML（变量名统一为 user_message_text；可选 attachments）
_USER_MESSAGE_QUERY_SNIPPET = """
<user_message>
  <query>{{ user_message_text|e }}</query>
  {%- if attachments %}
  <attachment_context>
  {%- for attachment in attachments %}
    <attachment index="{{ loop.index }}" file_id="{{ attachment.file_id|e }}" file_name="{{ attachment.file_name|e }}">
{{ attachment.text|e }}
    </attachment>
  {%- endfor %}
  </attachment_context>
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
{%- if not mcp_auto_mode %}
  <selected_mcp_servers>
{%- for server in mcp_configs %}
    <server id="{{ server.id|e }}">{{ server.description|e }}</server>
{%- endfor %}
  </selected_mcp_servers>
{%- endif %}
  <rules>
    <rule>避免重复调用: 不要使用相似查询多次调用 web_search，不要重复提取已提取过的 URL</rule>
    <rule>检查历史工具调用结果: 在调用工具前，仔细检查历史工具调用结果是否已足够回答问题。如果已获得足够信息，请直接给出最终回答并停止调用更多工具。</rule>
  </rules>
  <context>
    <current_datetime>{{ current_datetime|e }}</current_datetime>
    {%- if client_ip %}
    <client_ip>{{ client_ip|e }}</client_ip>
    {%- endif %}
  </context>
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

disabled_tools_message_template: Template = Template(
    """
以下工具已达到最大调用次数上限，当前不可再调用: {{ ', '.join(disabled_tools) }}.
""".strip()
)

gentle_tips_in_web_search_template: Template = Template(
    """
目前已经调用了 web search 工具，工具返回内容中已经包含了和用户查询相关的片段。
- 除非你需要完整的网页内容，否则不要再调用 web_pages_extract 工具
""".strip()
)

tool_call_sufficient_info_template: Template = Template(
    """
⚠️ 重要提示: 根据历史工具调用结果，你可能已经获得了足够的信息来回答用户问题。

请仔细检查：
1. 已调用的工具及其返回结果
2. 这些结果是否已经包含了回答用户问题所需的信息
3. 如果结果已足够，请直接给出最终回答，并停止调用更多工具

避免不必要的重复调用，特别是：
- 使用相似查询多次调用 web_search
- 重复提取已提取过的 URL
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
