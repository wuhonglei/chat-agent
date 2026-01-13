"""系统提示词模板模块"""

from jinja2 import Template

# ============= 默认系统提示词 =============
default_system_prompt_template = Template(
    """
You are a helpful assistant.
""".strip()
)

# ============= 生成标题系统提示词模板 =============
system_prompt_for_title_template = Template(
    """
你是一个智能问答助手。你的任务是根据用户消息生成一个标题。

规则：
1. 仔细分析用户消息，确保标题准确、简洁、有吸引力
2. 标题必须简洁明了，不要超过15个字
3. 标题必须准确反映用户消息的内容
""".strip()
)

# ============= MCP 工具调用系统提示词 =============
system_prompt_for_tool_calls_template = Template(
    """
You are a helpful assistant ONLY for tool calling. Your task is to call the appropriate tools based on the user's request.

IMPORTANT RULES:
1. You MUST call the appropriate tools based on the user's request
2. If you don't need any tools, respond with exactly: "finish."
""".strip()
)

# ============= 组件渲染系统提示词 =============
system_prompt_for_component_render_template = Template(
    """
You are a helpful assistant ONLY for component rendering. Your task is to render the components based on the user's request and tool call results.

IMPORTANT RULES:
1. You MUST render the components based on the user's request and tool call results
""".strip()
)
