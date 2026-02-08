"""用户消息提示词模板模块"""

from jinja2 import Template

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template: Template = Template(
    """
{{ user_message }}

{% if not mcp_auto_mode %}
用户为此请求手动选择了以下工具：
    {% for server in mcp_configs %}
    - {{ server.id }}: {{ server.description }}
    {% endfor %}
{% endif %}
重要规则：
- 如果没有合适的工具，请回复"finish."
- 你只负责调用工具。请勿提供最终答案。只需调用合适的工具或回复"finish."
- 工具选择必须与用户问题高度相关。如果用户问题与可用工具不相关，请回复"finish."
- 避免重复调用：不要使用相似查询多次调用 web_search，不要重复提取已提取过的 URL
- 在调用工具前，仔细检查历史工具调用结果是否已足够回答问题。如果已获得足够信息，请回复"finish."
- 当前时间：{{ current_datetime }}.
{% if client_ip %}- 客户端IP：{{ client_ip }}.{% endif %}
""".strip()
)

user_message_for_title_template: Template = Template(
    """
用户消息：{{ user_message }}
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

# 仅组件数据块（供 get_component_block 拼接用）
component_data_block_template: Template = Template(
    """
{% if component_data %}
请在文本中合适位置返回 markdown 格式的 json 组件数据:
{% for component in component_data %}
{{ loop.index }}. 组件名称：{{ component.component_name }}
组件描述：{{ component.component_description }}
```json
{{ component.component_json_str }}
```

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
3. 如果结果已足够，请回复 "finish"，不要再调用更多工具

避免不必要的重复调用，特别是：
- 使用相似查询多次调用 web_search
- 重复提取已提取过的 URL
""".strip()
)

final_response_message_template: Template = Template(
    """
{% if tool_result %}{{ tool_result }}{% endif %}
{% if component_data %}{{ component_data }}{% endif %}
{% if tool_result or component_data %}请基于以上信息回答以下用户问题：

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

USER_FACTS_PREFERENCES_PROMPT: Template = Template(
    """根据以下对话内容，提炼用户的**可验证事实**与**明确偏好**。

要求：
1. 仅输出可验证事实与明确偏好，不要编造。
2. 事实示例：在北京工作、用 Python 3.10、项目名为 XX。
3. 偏好示例：偏好简短回答、不要用代码块、希望用中文。
4. 已有记录（可在此基础上合并或去重）：
   - 已有事实: {{ existing_facts }}
   - 已有偏好: {{ existing_preferences }}
5. 输出格式（JSON，不要其他说明）：
{"facts": ["事实1", "事实2"], "preferences": ["偏好1", "偏好2"]}

对话内容：
---
[用户]: {{ user_message_content }}

[助手]: {{ assistant_content }}
{% if summary %}

[较早轮次摘要]: {{ summary }}{% endif %}
---
""".strip()
)
