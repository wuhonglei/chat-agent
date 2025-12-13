from app.mcp.mcp_client import mcp_config_for_fe
from app.models.llm import ToolCallMessage
from app.utils.common import has_tool_call_with_name
from app.utils.date import get_current_date, get_current_datetime_str
from jinja2 import Template

# ============= 系统提示词 =============

default_system_prompt_template = Template("""
You are a helpful assistant.
""".strip())


# ============= 工具调用系统提示词 =============
system_prompt_for_tool_calls_template = Template("""
You are a helpful assistant ONLY for tool calling. Your role is to analyze the user's request and determine which tools to call.

IMPORTANT RULES:
1. You MUST NOT provide the final answer to the user's question
2. You MUST NOT explain or interpret the results
3. You MUST ONLY call the appropriate tools based on the user's request
4. If you don't need any tools, respond with exactly: "finish."
5. Do not add any additional text, explanations, or commentary
6. Your response should be minimal and focused only on tool calling

Your task is to call tools, not to answer questions directly.
""".strip())

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


# 根据用户消息和模型回答生成标题系统提示词模板(中文)
system_prompt_for_title_template = Template("""
你是一个智能问答助手。你的任务是根据用户消息生成一个标题。

规则：
1. 仔细分析用户消息，确保标题准确、简洁、有吸引力
2. 标题必须简洁明了，不要超过15个字
3. 标题必须准确反映用户消息的内容
""".strip())

user_message_for_title_template = Template("""
用户消息：{{ user_message }}
""".strip())

user_message_for_weather_component_template = Template("""
请根据上面天气工具调用结果生成天气组件的 props 数据, 用于辅助用户理解天气情况, 组件 props 数据格式为：
{
  location: "城市名称"
  data: { /* WeatherNow 类型的所有字段 */ },
}

具体要求：
1. data 对象必须包含：
   - obsTime: 使用当前时间或模拟时间（ISO 格式）
   - temp: "20" （当前温度，字符串格式）
   - feelsLike: "体感温度"
   - icon: "100" （天气图标代码）
   - text: "晴/多云/雨等"
   - wind360: "180"
   - windDir: "南风"
   - windScale: "3"
   - windSpeed: "12"
   - humidity: "65"
   - precip: "0.0"
   - pressure: "1013"
   - vis: "10"
   - cloud: "25"
   - dew: "15"
   - tempMin?: "18"
   - tempMax?: "22"

2. location: 生成一个中国城市名称，如"北京市"

输出示例：
```component_weather
{
  location: "北京市",
  data: {
    obsTime: "2025-12-07T12:00:00+08:00",
    temp: "20",
    feelsLike: "18",
    icon: "100",
    text: "晴",
    wind360: "180",
    windDir: "南风",
    windScale: "3",
    windSpeed: "12",
    humidity: "65",
    precip: "0.0",
    pressure: "1013",
    vis: "10",
    cloud: "25",
    dew: "15",
    tempMin: "18",
    tempMax: "22",
    fxLink: "https://www.qweather.com/weather/beijing-101010100.html"
  }
}
```
""".strip())

# ============= 系统提示词和用户消息提示词字典 =============
system_prompt_dict = {
    'default': default_system_prompt_template,
    'for_tool_calls': system_prompt_for_tool_calls_template,
    'for_title': system_prompt_for_title_template,
}

user_message_prompt_dict = {
    'for_tool_calls': user_message_for_tool_call_template,
    'for_title': user_message_for_title_template,
    'for_weather_component': user_message_for_weather_component_template,
}


def get_default_system_prompt(include_date: bool) -> str:
    """Get default system prompt with current time information"""
    if include_date:
        current_datetime = get_current_datetime_str()
        current_date = get_current_date()
        return system_prompt_dict['default'].render(current_datetime=current_datetime, current_date=current_date)
    else:
        return system_prompt_dict['default'].render()


def get_user_message_for_component_render(user_message: str, tool_call_messages: list[ToolCallMessage]) -> str:
    """Get user message for component render"""
    has_weather_tool_call = has_tool_call_with_name(
        tool_call_messages, 'weather')
    if not has_weather_tool_call:
        return user_message

    user_messages = [
        f'用户消息: {user_message}',
    ]

    user_messages.append(
        user_message_prompt_dict['for_weather_component'].render())
    return '\n'.join(user_messages)


def get_prompt_with_mcp_servers(user_message: str, mcp_auto_mode: bool, server_names: list[str], client_ip: str | None) -> tuple[str, str]:
    id_by_config = {config['id']: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [id_by_config[server_name]
                   for server_name in server_names if server_name in id_by_config]
    system_prompt = system_prompt_dict['for_tool_calls'].render()
    new_user_message = user_message_prompt_dict['for_tool_calls'].render(
        user_message=user_message, mcp_auto_mode=mcp_auto_mode, mcp_configs=mcp_configs, current_datetime=get_current_datetime_str(), client_ip=client_ip)
    return system_prompt, new_user_message


def get_prompt_for_title(user_message: str) -> tuple[str, str]:
    new_system_prompt = system_prompt_dict['for_title'].render()
    new_user_message = user_message_prompt_dict['for_title'].render(
        user_message=user_message)
    return new_system_prompt, new_user_message
