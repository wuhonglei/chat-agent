"""用户消息提示词模板模块"""

from jinja2 import Template

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template: Template = Template(
    """
<tool_call_user_message>
  <user_query>{{ user_message|e }}</user_query>
{% if not mcp_auto_mode %}
  <selected_mcp_servers>
{% for server in mcp_configs %}
    <server id="{{ server.id|e }}">{{ server.description|e }}</server>
{% endfor %}
  </selected_mcp_servers>
{% endif %}
  <rules>
    <rule>避免重复调用: 不要使用相似查询多次调用 web_search，不要重复提取已提取过的 URL</rule>
    <rule>检查历史工具调用结果: 在调用工具前，仔细检查历史工具调用结果是否已足够回答问题。如果已获得足够信息，请直接给出最终回答并停止调用更多工具。</rule>
  </rules>
  <context>
    <current_datetime>{{ current_datetime|e }}</current_datetime>{% if client_ip %}
    <client_ip>{{ client_ip|e }}</client_ip>{% endif %}
  </context>
</tool_call_user_message>
""".strip()
)

user_message_for_title_template: Template = Template(
    """
<user_message>
  <query>{{ user_message|e }}</query>
</user_message>
""".strip()
)

# MCP 工具调用结果渲染（供 format_mcp_tool_results_for_user_message 使用）
# mcp_tool_items: [{"name": str, "args": str, "content": str}, ...]
mcp_block_template: Template = Template(
    """
{% if mcp_tool_items %}
【以下为 MCP 工具调用返回的结果】

{% for item in mcp_tool_items %}
### {{ item.name }}
参数：{{ item.args }}

返回：
{{ item.content }}
{% if not loop.last %}

---

{% endif %}
{% endfor %}
{% endif %}""".strip()
)

disabled_tools_message_template: Template = Template(
    """
以下工具已达到5次调用上限，当前不可再调用: {{ ', '.join(disabled_tools) }}.
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

final_response_message_template: Template = Template(
    """
{% if tool_result %}{{ tool_result }}{% endif %}
{% if tool_result %}请基于以上信息回答以下用户问题：

{% endif %}用户问题：{{ user_message }}
""".strip()
)

# ============= 上下文摘要相关提示词 =============
WINDOW_OUT_SUMMARY_PROMPT: Template = Template(
    """请根据以下被截断的较早对话内容，生成一段简短摘要。

要求：
1. 只归纳「用户问了什么、助手答了什么」的关键信息，不要编造。
2. 用自然语言、控制在 {{ max_tokens_hint }} 字以内。
3. 若内容为空或无关紧要，可回复「无」。

被截断的对话内容：
---
{{ text }}
---
""".strip()
)

WINDOW_OUT_SUMMARY_MERGE_PROMPT: Template = Template(
    """请将「已有摘要」与「新增对话内容」合并为一段简短摘要。

要求：
1. 保留已有摘要的关键信息，并融入新增对话的要点，不要编造。
2. 用自然语言、控制在 {{ max_tokens_hint }} 字以内。
3. 若新增内容为空或无关紧要，可主要保留已有摘要并略作精简。

已有摘要：
---
{{ prior_summary }}
---

新增对话内容：
---
{{ new_messages_text }}
---
""".strip()
)
