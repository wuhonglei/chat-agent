"""用户消息提示词模板模块"""
from jinja2 import Template

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template = Template("""
{{ user_message }}

{% if not mcp_auto_mode %}
User has manually selected the following tools for this request:
    {% for server in mcp_configs %}
    - {{ server.id }}: {{ server.description }}
    {% endfor %}
{% endif %}
IMPORTANT RULES:
- If none of the selected tools are suitable, respond with "finish."
- You are ONLY responsible for calling tools. Do NOT provide the final answer. Just call the appropriate tools or respond with "finish."
- Current datetime: {{ current_datetime }}.
- Client IP: {{ client_ip }}.
""".strip())

user_message_for_title_template = Template("""
用户消息：{{ user_message }}
""".strip())

user_message_with_component_data_template = Template("""
用户消息：{{ user_message }}

请在文本中合适位置返回 markdown 格式的 json 组件数据:
{% for component in component_data %}
{{ loop.index }}. 组件名称：{{ component.component_name }}
组件描述：{{ component.component_description }}
```json
{{ component.component_json_str }}
```

{% endfor %}
""".strip())
