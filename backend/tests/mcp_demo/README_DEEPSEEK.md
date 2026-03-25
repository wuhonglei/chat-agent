# DeepSeek + MCP Tools 集成示例

本示例展示如何将 DeepSeek API 与 MCP (Model Context Protocol) 工具集成，实现智能工具调用。

## 功能特点

- 🔧 **工具转换**: 自动将 MCP 工具格式转换为 OpenAI/DeepSeek 兼容格式
- 🤖 **智能调用**: DeepSeek 自动判断何时调用哪些工具
- 🔄 **迭代处理**: 支持多轮工具调用，直到获得最终答案
- 🌐 **多服务器支持**: 同时连接远程和本地 MCP 服务器

## 环境准备

### 1. 安装依赖

```bash
pip install openai fastmcp
```

### 2. 设置环境变量

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

或者在代码中直接修改：

```python
deepseek_client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://api.deepseek.com"
)
```

## 代码结构

### 核心函数

#### 1. `convert_mcp_tools_to_openai_format(mcp_tools)`

将 MCP 工具格式转换为 OpenAI/DeepSeek API 所需的工具格式。

**���数:**
- `mcp_tools`: MCP 工具列表

**返回:**
- OpenAI 格式的工具列表

**示例转换:**
```python
# MCP 工具格式
{
    "name": "get-weather",
    "description": "获取天气信息",
    "inputSchema": {...}
}

# 转换后的 OpenAI 格式
{
    "type": "function",
    "function": {
        "name": "get-weather",
        "description": "获取天气信息",
        "parameters": {...}
    }
}
```

#### 2. `execute_mcp_tool(client, tool_name, arguments)`

执行指定的 MCP 工具并返回结果。

**参数:**
- `client`: MCP 客户端实例
- `tool_name`: 工具名称
- `arguments`: 工具参数字典

**返回:**
- 工具执行结果（字符串格式）

**处理逻辑:**
- 提取文本内容（支持多种结果格式）
- 异常处理和错误信息返回

#### 3. `chat_with_deepseek(client, deepseek_client, user_message, mcp_tools, max_iterations=5)`

使用 DeepSeek API 处理对话，自动调用 MCP 工具。

**参数:**
- `client`: MCP 客户端
- `deepseek_client`: DeepSeek API 客户端
- `user_message`: 用户输入的消息
- `mcp_tools`: 可用的 MCP 工具列表
- `max_iterations`: 最大迭代次数（默认 5）

**工作流程:**
1. 将 MCP 工具转换为 DeepSeek 可用格式
2. 发送用户消息给 DeepSeek
3. 检查 DeepSeek 是否需要调用工具
4. 如果需要，执行工具并将结果返回给 DeepSeek
5. 重复步骤 3-4，直到获得最终答案

## 使用示例

### 基础用法

```python
import asyncio
from openai import OpenAI
from fastmcp import Client
from fastmcp.client.transports import MCPConfig

async def main():
    # 1. 配置 MCP 服务器
    config = {
        "mcpServers": {
            "weather-mcp": {
                "command": "python3",
                "args": ["-m", "mcp_demo.weather_mcp.weather_server", "--transport", "stdio"],
            }
        }
    }

    # 2. 创建客户端
    mcp_config = MCPConfig.from_dict(config)
    client = Client(transport=mcp_config)

    deepseek_client = OpenAI(
        api_key="your-api-key",
        base_url="https://api.deepseek.com"
    )

    async with client:
        # 3. 获取工具列表
        tools = await client.list_tools()

        # 4. 调用 DeepSeek
        await chat_with_deepseek(
            client=client,
            deepseek_client=deepseek_client,
            user_message="北京今天天气怎么样？",
            mcp_tools=tools
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 运行示例

```bash
cd /Users/honglei.wu/Desktop/code/ai-doc/backend
python -m tests.mcp_demo.mcp_client
```

## 执行流程示例

### 示例 1: 查询天气

**输入:**
```
北京今天天气怎么样？
```

**执行流程:**
```
1. 用户消息发送给 DeepSeek
2. DeepSeek 决定调用 weather-mcp__get-weather 工具
3. 执行工具并返回天气数据
4. DeepSeek 根据数据生成最终回复
```

**输出:**
```
============================================================
用户: 北京今天天气怎么样？
============================================================

--- 迭代 1 ---

需要调用 1 个工具:

调用工具: weather-mcp__get-weather
参数: {
  "city": "北京"
}
结果: 北京今天天气: 晴朗，温度 20°C

--- 迭代 2 ---

============================================================
DeepSeek 回复: 北京今天天气晴朗，温度约为 20°C。
============================================================
```

### 示例 2: 网络搜索

**输入:**
```
搜索一下 2024 年人工智能的最新进展
```

**执行流程:**
```
1. 用户消息发送给 DeepSeek
2. DeepSeek 决定调用 tavily-remote-mcp__search 工具
3. 执行搜索工具并返回结果
4. DeepSeek 总结搜索结果并生成回复
```

## 配置说明

### MCP 服务器配置

```python
config = {
    "mcpServers": {
        # 远程 HTTP 服务器
        "tavily-remote-mcp": {
            "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY",
            "transport": "http",
        },
        # 本地 stdio 服务器
        "weather-mcp": {
            "command": "python3",
            "args": ["-m", "mcp_demo.weather_mcp.weather_server", "--transport", "stdio"],
        }
    }
}
```

### DeepSeek 配置

```python
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 调用参数
response = deepseek_client.chat.completions.create(
    model="deepseek-chat",        # 模型名称
    messages=messages,             # 对话历史
    tools=openai_tools,           # 可用工具列表
    tool_choice="auto"            # 自动决定是否调用工具
)
```

## 工具调用流程图

```
用户输入
   ↓
DeepSeek API
   ↓
需要工具? ──→ 否 ──→ 返回答案
   ↓
   是
   ↓
MCP 工具执行
   ↓
返回结果给 DeepSeek
   ↓
DeepSeek 处理结果
   ↓
需要继续调用工具? ──→ 是 ──→ 循环
   ↓
   否
   ↓
返回最终答案
```

## 注意事项

1. **API Key**: 确保设置了有效的 DeepSeek API Key
2. **工具格式**: MCP 工具必须有 `inputSchema` 才能被正确转换
3. **迭代次数**: 复杂查询可能需要多次工具调用，建议设置合理的 `max_iterations`
4. **错误处理**: 工具执行失败会返回错误信息，不会中断整个流程
5. **结果解析**: 不同工具返回格式不同，代码已处理常见格式

## 扩展功能

### 添加自定义工具

```python
# 在 MCP 服务器中添加工具
@mcp.tool()
async def custom_tool(param1: str, param2: int) -> str:
    """自定义工具描述"""
    # 工具逻辑
    return result
```

### 调整 DeepSeek 参数

```python
response = deepseek_client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=openai_tools,
    tool_choice="auto",
    temperature=0.7,              # 控制创造性
    max_tokens=2000,              # 最大输出长度
)
```

## 故障排查

### 问题 1: 工具调用失败

**原因**: 工具名称或参数不匹配

**解决**: 检查工具定义和 DeepSeek 调用的参数

### 问题 2: 达到最大迭代次数

**原因**: DeepSeek 持续调用工具但未给出最终答案

**解决**: 增加 `max_iterations` 或优化工具描述

### 问题 3: API 调用超时

**原因**: 网络问题或工具执行时间过长

**解决**: 添加超时处理和重试机制

## 相关资源

- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [MCP 协议规范](https://modelcontextprotocol.io/)
