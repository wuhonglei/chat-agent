from jinja2 import Template
from datetime import datetime
from app.mcp.mcp_client import mcp_config_for_fe
from app.utils.common import get_current_datetime_str, get_current_date

default_system_prompt_template = Template("""
You are a helpful assistant.
Current date and time: {{ current_datetime }}
When providing information about current events, versions, or time-sensitive topics, always use the current date {{ current_date }} as reference.
""".strip())

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
You are a helpful assistant ONLY for tool calling. Your role is to analyze the user's request and determine which tools to call.

Current date and time: {{ current_datetime }}.

IMPORTANT RULES:
1. You MUST NOT provide the final answer to the user's question
2. You MUST NOT explain or interpret the results
3. You MUST ONLY call the appropriate tools based on the user's request
4. If you don't need any tools, respond with exactly: "finish."
5. Do not add any additional text, explanations, or commentary
6. Your response should be minimal and focused only on tool calling
7. When calling search tools, use the current date {{ current_date }} for time-sensitive queries

Your task is to call tools, not to answer questions directly.
""".strip())

user_message_template = Template("""
User has made a request:
{{ user_message }}

{% if not mcp_auto_mode %}
User has manually selected the following tools for this request:
    {% for server in mcp_configs %}
    - {{ server.id }}: {{ server.description }}
    {% endfor %}
{% endif %}
IMPORTANT RULES:
- If none of the selected tools are suitable, respond with "finish.
- You are ONLY responsible for calling tools. Do NOT provide the final answer. Just call the appropriate tools or respond with "finish."
""".strip())


def get_default_system_prompt() -> str:
    """Get default system prompt with current time information"""
    current_datetime = get_current_datetime_str()
    current_date = get_current_date()
    return default_system_prompt_template.render(
        current_datetime=current_datetime, current_date=current_date)


def get_prompt_with_mcp_servers(user_message: str, mcp_auto_mode: bool, server_names: list[str]) -> tuple[str, str]:
    id_by_config = {config['id']: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [id_by_config[server_name]
                   for server_name in server_names if server_name in id_by_config]
    system_prompt = mcp_servers_prompt_template.render(
        current_datetime=get_current_datetime_str(), current_date=get_current_date())
    new_user_message = user_message_template.render(
        user_message=user_message, mcp_auto_mode=mcp_auto_mode, mcp_configs=mcp_configs)
    return new_user_message, system_prompt
