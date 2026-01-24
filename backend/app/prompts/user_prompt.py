"""用户消息提示词模板模块"""

from jinja2 import Template

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template = Template(
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

user_message_for_title_template = Template(
    """
用户消息：{{ user_message }}
""".strip()
)

user_message_with_component_data_template = Template(
    """
用户消息：{{ user_message }}

请在文本中合适位置返回 markdown 格式的 json 组件数据:
{% for component in component_data %}
{{ loop.index }}. 组件名称：{{ component.component_name }}
组件描述：{{ component.component_description }}
```json
{{ component.component_json_str }}
```

{% endfor %}
""".strip()
)


disabled_tools_message_template = Template(
    """
以下工具已达到5次调用上限，当前不可再调用: {{ ', '.join(disabled_tools) }}.
""".strip()
)

gentle_tips_in_web_search_template = Template(
    """
目前已经调用了 web search 工具，工具返回内容中已经包含了和用户查询相关的片段。
- 除非你需要完整的网页内容，否则不要再调用 web_pages_extract 工具
""".strip()
)

tool_call_sufficient_info_template = Template(
    """
⚠️ 重要提示：根据历史工具调用结果，你可能已经获得了足够的信息来回答用户问题。

请仔细检查：
1. 已调用的工具及其返回结果
2. 这些结果是否已经包含了回答用户问题所需的信息
3. 如果结果已足够，请回复 "finish"，不要再调用更多工具

避免不必要的重复调用，特别是：
- 使用相似查询多次调用 web_search
- 重复提取已提取过的 URL
""".strip()
)
