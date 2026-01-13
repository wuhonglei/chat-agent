from jinja2 import Template

# 你的原始模板
original_template = Template(
    """
You are a helpful assistant just for MCP tools calling.
User has made a request and manually selected the following MCP servers:
{% if not mcp_auto_mode %}
    {% for server in mcp_configs %}
    - {{ server.id }}: {{ server.description }}
    {% endfor %}
{% endif %}
"""
)

# 测试数据
test_data = {
    "mcp_auto_mode": False,
    "mcp_configs": [
        {"id": "server1", "description": "Database access server"},
        {"id": "server2", "description": "File system server"},
    ],
}

try:
    result = original_template.render(**test_data)
    print("✅ 模板渲染成功:")
    print(result)
except Exception as e:
    print(f"❌ 模板渲染失败: {e}")
