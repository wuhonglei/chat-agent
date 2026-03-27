# MCP 配置与加载机制说明（当前实现）

## 1. 目标

本文档用于说明当前后端如何加载和管理 MCP（Model Context Protocol）服务配置，重点回答：

- MCP 服务从哪里来；
- 哪些服务是本地 FastMCP，哪些是远程配置；
- 前端如何拿到 MCP 配置与在线状态；
- 文档与历史方案的边界。

## 2. 当前 MCP 服务清单

在 `app/mcp/mcp_client.py` 中，当前注册的服务为：

- `ip-locator-mcp`（本地 FastMCP）
- `time-mcp`（本地 FastMCP）
- `context7-mcp`（远程配置，来自 `settings.mcp.context7_mcp`）
- `weather-mcp`（本地 FastMCP）
- `tavily-mcp`（本地 FastMCP）
- `code-exec-mcp`（本地 FastMCP）

> 说明：当前主应用不包含 `confluence_mcp` 的运行时注册。

## 3. 配置来源

### 3.1 主配置入口

- 后端统一配置在 `app/core/config.py` 的 `settings` 中加载；
- `context7-mcp` 的连接信息通过 `settings.mcp.context7_mcp` 注入到 `mcp_config`；
- 其余本地 MCP 通过 Python 直接导入 server 实例注册。

### 3.2 本地/远程服务的区分

`MCPClientManager.initialize()` 根据 server 配置类型自动选择传输层：

- `FastMCP` 实例：`FastMCPTransport`
- 字典且含 `url`：`StreamableHttpTransport`
- 字典且含 `command`：`StdioTransport`

这意味着 `context7-mcp` 可作为远程 HTTP 服务接入，而本地服务走进程内 FastMCP。

## 4. 运行时管理机制

`MCPClientManager` 的核心职责：

1. 初始化所有 MCP 客户端连接；
2. 拉取并缓存工具列表（`tools_by_server`）；
3. 维护 `tool_name -> server_name` 映射（`tools_map`）；
4. 根据工具 schema 过滤无效参数后调用工具；
5. 提供健康检查与前端配置输出。

## 5. 前端配置输出

前端通过健康接口获取 `mcp_config_for_fe`（ID、名称、描述、图标、在线状态），该列表同样定义于 `app/mcp/mcp_client.py`。

在线状态由 `health_check()` 结果回填，供前端展示 MCP 可用性。

## 6. 与历史文档差异

以下内容属于历史方案或已不适配当前代码，已从“当前实现”口径中剔除：

- `confluence_mcp` 作为现网服务的描述；
- 依赖 `inject_mcp_env_vars` 作为主加载链路的描述；
- 与现有 `mcp_client.py` 不一致的 server 列表或初始化顺序假设。

## 7. 建议维护方式

- 所有“当前实现”类文档应以 `app/mcp/mcp_client.py` 为准；
- 若新增 MCP 服务，需同步更新：
  - `mcp_config`；
  - `mcp_config_for_fe`；
  - 健康检查与前端展示说明文档；
- 规划中的配置重构（如统一 schema 字段）建议单独归档为“规划方案”文档，避免与现网说明混淆。
