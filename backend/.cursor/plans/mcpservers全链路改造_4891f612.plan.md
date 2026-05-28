---
name: MCPServers全链路改造
overview: 将现有 `settings.mcp` 下分散的 MCP 子配置破坏性替换为标准 `mcpServers` 结构，并同步改造运行时消费链路与示例配置，确保加载、注册、连接与调用都基于统一模型。
todos:
  - id: schema-unify
    content: 在 app/schemas/config.py 定义统一 MCPServerConfig，并将 MCPConfig 改为 mcpServers 映射，删除旧 *_mcp 字段
    status: pending
  - id: runtime-refactor
    content: 重构 registry/connection_pool/client 以 mcpServers 为唯一来源，支持 stdio 与 streamableHttp
    status: pending
  - id: server-config-adapt
    content: 调整各 mcp_servers/*/config.py 的读取逻辑，从 mcpServers 与 env 字段解包业务参数
    status: pending
  - id: config-doc-migrate
    content: 迁移 nacos 示例与相关 README 到 mcpServers 格式并清理旧字段说明
    status: pending
  - id: verify-smoke
    content: 执行最小冒烟验证：配置加载、服务注册、至少两类 transport 的工具调用可用
    status: pending
isProject: false
---

# MCP 配置统一为 mcpServers（破坏性全链路）

## 目标
将 `app/schemas/config.py` 中当前的 `context7_mcp`、`weather_mcp`、`tavily_mcp`、`time_mcp`、`code_exec_mcp` 等字段，统一为标准 `mcpServers` 映射结构（`name -> server config`），并让运行时代码完全从 `mcpServers` 读取。

## 改造范围
- 配置模型：[`/Users/honglei.wu/Desktop/code/chat-agent/backend/app/schemas/config.py`](/Users/honglei.wu/Desktop/code/chat-agent/backend/app/schemas/config.py)
- 配置加载入口：[`/Users/honglei.wu/Desktop/code/chat-agent/backend/app/core/config.py`](/Users/honglei.wu/Desktop/code/chat-agent/backend/app/core/config.py)
- MCP 注册与连接：[`/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/registry.py`](/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/registry.py)、[`/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/connection_pool.py`](/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/connection_pool.py)、[`/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/client.py`](/Users/honglei.wu/Desktop/code/chat-agent/backend/app/mcp/client.py)
- 各 MCP 服务配置消费点：`app/mcp/mcp_servers/*/config.py`（按需）
- 示例配置与文档：[`/Users/honglei.wu/Desktop/code/chat-agent/backend/nacos-data/config/ai-chat-dev@@DEFAULT_GROUP@@`](/Users/honglei.wu/Desktop/code/chat-agent/backend/nacos-data/config/ai-chat-dev@@DEFAULT_GROUP@@) 及相关 README

## 设计方案
1. 在 `schemas` 引入标准 MCP Server 配置模型（建议）
   - 新增统一模型（示意）：
     - `enabled: bool`
     - `type: Literal["stdio", "streamableHttp"]`（可为远程 URL 场景提供默认）
     - `url: str | None`
     - `command: str | None`
     - `args: list[str]`
     - `env: dict[str, str]`
     - `headers: dict[str, str]`
     - `description: str | None`
     - `verify_ssl: bool`
   - 在 `MCPConfig` 中改为：`mcpServers: dict[str, MCPServerConfig]`
   - 删除旧字段：`context7_mcp/weather_mcp/tavily_mcp/time_mcp/code_exec_mcp`（按你的破坏性替换要求）。

2. 运行时注册链路统一读取 `settings.mcp.mcpServers`
   - `registry.py`：改为遍历 `mcpServers` 生成 registry；统一使用 server key（如 `deepwiki`、`codegraph`、`zread`、`github`）。
   - `connection_pool.py`：按 `type` 分支创建 transport，保证 `headers/env/verify_ssl` 真实生效。
   - `client.py`：保留 `gateway` 行为配置，不再依赖旧 server 字段名。

3. 本地内置 MCP 的处理策略
   - `time/weather/tavily/code_exec` 不再从专属 `*_mcp` 字段取配置，而是改为从 `mcpServers[serverName]` 读取标准字段。
   - 对必须的业务参数（如天气 API key）使用 `env` 承载并在对应 `config.py` 解包，避免再次引入非标准顶级字段。

4. 配置源与示例同步
   - 更新 Nacos 示例为 `mcp.mcpServers` 结构（按你给的标准示例风格）。
   - 清理文档中旧字段命名（`context7_mcp` 等）与过时说明，避免误导。

5. 验证与回归
   - 启动阶段：验证 settings 能成功构建（无旧字段依赖）。
   - MCP 连接：验证 `streamableHttp` 与 `stdio` 两类 server 都可加载。
   - 功能回归：至少覆盖一个远程 MCP（如 `zread`）和一个 stdio MCP（如 `codegraph`）的工具可见性与调用成功。

## 风险与控制
- 破坏性替换会使旧环境变量/Nacos 键失效：通过一次性更新示例与启动前检查降低风险。
- 敏感信息（token/header）进入配置文件风险：建议在示例中用占位符，真实值走环境变量注入到 `env/headers`。
- `verify_ssl` 历史上存在“配置未生效”问题：本次在连接层明确打通并加日志确认。

## 交付结果
- `MCPConfig` 仅保留 `mcpServers` + `gateway`。
- 代码中不再出现对 `settings.mcp.context7_mcp/weather_mcp/...` 的读取。
- Nacos/文档示例完全切换到标准 MCP server 配置格式。
