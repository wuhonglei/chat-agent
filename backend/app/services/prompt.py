from jinja2 import Template
from app.mcp.mcp_client import mcp_config_for_fe


default_system_prompt = """You are a helpful assistant."""

system_prompt_with_references = """
你是一个智能问答助手。你的任务是基于提供的参考资料回答用户的问题。

规则：
1. 仔细分析提供的参考资料，这些资料可能来自知识库文档或实时网络搜索
2. 如果是网络搜索结果，请注意信息的时效性和来源可靠性
3. 在回答中必须使用引用标记 [^CITE:n] 来标注信息来源，其中 n 是参考资料的编号
4. 当引用某个来源的信息时，在相关内容后添加 [^CITE:n] 格式的引用标记
5. 如果综合多个来源，请分别标注各自的引用编号，如 [^CITE:1][^CITE:2]
6. 如果参考资料中没有相关信息，请诚实告知用户，并根据你的知识提供可能的建议
7. 保持回答准确、专业、有条理
8. 优先使用参考资料中的信息，确保答案的准确性

引用示例：
根据资料显示，Python 是一种高级编程语言[^CITE:1]，它具有简洁易读的语法特点[^CITE:2]。
""".strip()


mcp_servers_prompt_template = Template("""
You are a helpful assistant just for tools calling.
{% if not mcp_auto_mode %}
User has made a request and manually selected the following tools:
    {% for server in mcp_configs %}
    - {{ server.id }}: {{ server.description }}
    {% endfor %}
{% endif %}

note:
- if you do not need any tools to call, you should just tell the user 'I have no need to call any tools.' without any other words.
""".strip())

user_message_template = Template(f"""
User has made a request:
{{ user_message }}

note:
- if you do not need any tools to call, you should just tell the user 'I have no need to call any tools.' without any other words.
""".strip())


def get_prompt_with_mcp_servers(user_message: str, mcp_auto_mode: bool, server_names: list[str]) -> tuple[str, str]:
    id_by_config = {config['id']: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [id_by_config[server_name]
                   for server_name in server_names if server_name in id_by_config]
    new_user_message = user_message_template.render(user_message=user_message)
    system_prompt = mcp_servers_prompt_template.render(
        mcp_auto_mode=mcp_auto_mode, mcp_configs=mcp_configs)
    return new_user_message, system_prompt
