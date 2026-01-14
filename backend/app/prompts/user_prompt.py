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
- 当前时间：{{ current_datetime }}.
- 客户端IP：{{ client_ip }}.
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
以下工具已达到最大迭代次数，已被禁用, 请不要再尝试调用它们：
{% for tool in disabled_tools %}- {{ tool }}
{% endfor %}
""".strip()
)
