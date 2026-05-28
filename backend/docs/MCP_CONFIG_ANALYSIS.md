# MCP 配置与加载机制说明（当前实现）

## 1. 目标

本文档用于说明当前后端如何加载和管理 MCP（Model Context Protocol）服务配置，重点回答：

- MCP 服务从哪里来；
- 哪些服务是本地 FastMCP，哪些是远程配置；
- 如何通过配置控制 Server 的启用/禁用；
- 文档与历史方案的边界。

## 2. 当前 MCP 服务清单

由 `settings.mcp.servers` 配置驱动（默认值见 `app/schemas/config.py` 的 `MCPConfig.servers`）：

| Server 名称 | 传输方式 | 模块路径 | 说明 |
|---|---|---|---|
| `time-mcp` | fastmcp | `app.mcp.mcp_servers.time_mcp.server` | 时间查询 |
| `weather-mcp` | fastmcp | `app.mcp.mcp_servers.weather_mcp.server` | 天气查询 |
| `tavily-mcp` | fastmcp | `app.mcp.mcp_servers.tavily_mcp.server` | 联网搜索 |
| `code-exec-mcp` | fastmcp | `app.mcp.mcp_servers.code_exec_mcp.server` | 代码执行沙箱 |
| `file-mcp` | fastmcp | `app.mcp.mcp_servers.file_mcp.server` | 文件操作 |
| `shell-mcp` | fastmcp | `app.mcp.mcp_servers.shell_mcp.server` | Shell 命令执行 |
| `context7-mcp` | http | `url` + `headers`（见 `mcp.servers`） | Context7 文档检索 |

## 3. 配置驱动机制

### 3.1 核心配置：`mcp.servers`

`MCPConfig.servers` 是一个 `dict[str, MCPServerEntry]`，每个 entry 定义：

```python
class MCPServerEntry(BaseModel):
    enabled: bool = True                    # 是否启用
    transport: "fastmcp" | "http" | "stdio" # 传输方式
    module: str | None                      # fastmcp: Python 模块路径
    instance: str = "mcp"                   # fastmcp: FastMCP 实例属性名
    url: str | None                         # http: 远程 URL
    headers: dict[str, str]                 # http: 请求头
    command: str | None                     # stdio: 可执行文件
    args: list[str]                         # stdio: 命令行参数
    env: dict[str, str]                     # stdio: 环境变量
```

### 3.2 三种传输方式

| 传输 | 连接方式 | 使用场景 |
|---|---|---|
| `fastmcp` | 进程内通信（`FastMCPTransport`） | 本地 Python MCP Server，零网络开销 |
| `http` | 远程 HTTP（`StreamableHttpTransport`） | 远程 MCP Server |
| `stdio` | 子进程 stdin/stdout（`StdioTransport`） | 外部 MCP Server（npx、uvx 等） |

`MCPConnectionPool.initialize()` 根据 server 实例类型自动选择传输层：
- `FastMCP` 实例 → `FastMCPTransport`
- 字典且含 `url` → `StreamableHttpTransport`
- 字典且含 `command` → `StdioTransport`

### 3.3 配置来源

- 后端统一配置在 `app/core/config.py` 的 `settings` 中加载；
- 优先级（从高到低）：初始化参数 → 环境变量 → .env 文件 → Nacos 配置中心；
- 环境变量使用 `__` 作为嵌套分隔符，如 `MCP__SERVERS`。

### 3.4 禁用/启用 Server

在配置中设置 `enabled: false` 即可禁用某个 Server，无需修改代码：

```yaml
# .env 或 Nacos
MCP__SERVERS='{"weather-mcp": {"enabled": false}}'
```

或在 Python 配置中：
```python
mcp:
  servers:
    weather-mcp:
      enabled: false
```

### 3.5 新增 Server

新增 MCP Server 只需两步：

1. 在 `app/mcp/mcp_servers/<name>/server.py` 创建 FastMCP 实例；
2. 在 `mcp.servers` 配置中添加对应条目。

无需修改 `registry.py`、`connection_pool.py` 或其他代码。

## 4. 运行时管理机制

`MCPClientManager` 的核心职责：

1. 初始化所有 MCP 客户端连接（通过 `MCPConnectionPool`）；
2. 拉取并缓存工具列表（`tools_by_server`）；
3. 维护 `tool_name -> server_name` 映射（`tools_map`）；
4. 根据工具 schema 过滤无效参数后调用工具（`MCPToolGateway`）。

## 5. 与历史方案差异

- **旧方案**：`registry.py` 硬编码 import 所有 Server 实例；
- **新方案**：`registry.py` 从 `settings.mcp.servers` 读取配置，通过 `importlib` 动态加载；
- 行为完全等价，默认配置下加载的 Server 列表不变。

## 6. 建议维护方式

- Server 列表以 `settings.mcp.servers` 默认值为准（`app/schemas/config.py`）；
- 每个 Server 的业务参数（API Key 等）写在 `mcp.servers.<name>.env`（http 类用 `url`/`headers`）；`MCPRegistry` 加载 server 模块前调用对应 `mcp_servers/*/config.configure(entry)` 注入，各 server 通过 `get_config()` 读取；
- 若新增 MCP Server，需同步更新：
  - `MCPConfig.servers` 默认值；
  - 对应的 Server 实现模块。
