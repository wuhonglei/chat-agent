# MCP Server Config 实例化问题分析与优化

## 一、当前架构概览

### 1.1 配置来源与优先级（主应用）

- **app/core/config.py**：主 `Settings`，从 Nacos（YAML）、环境变量、初始化参数加载；`settings.mcp` 为 `MCPConfig`，内含 `tavily_mcp`、`weather_mcp`、`confluence_mcp` 等 `XxxMCPConfig`。
- **app/mcp/utils.inject_mcp_env_vars(mcp_config)**：从 `MCPConfig` 中抽出 `tavily_mcp`、`weather_mcp`、`confluence_mcp` 的**非 cache_config 字段**，用 `os.environ.setdefault(...)` 注入，便于各 MCP 的 `config.py` 通过 pydantic-settings 从环境变量读取。

### 1.2 各 MCP 的 config 实例化

- **tavily_mcp/config.py**、**confluence_mcp/config.py**、**weather_mcp/config.py** 等：定义各自的 `Settings`（pydantic-settings），`config = Settings()` 在**模块导入时**实例化。
- 读取来源：`env_file`（各 MCP 目录下的 `.env`）+ 环境变量（包括 `inject_mcp_env_vars` 注入的）。
- **mcp_client.py**：在**导入各 MCP server 之前**调用 `inject_mcp_env_vars(settings.mcp)`，保证 `config = Settings()` 时 `os.environ` 里已有从 Nacos 来的 `TAVILY_API_KEY`、`CONFLUENCE_*`、`QWEATHER_*` 等。

### 1.3 Nacos 中与 MCP 相关的结构（示例）

```yaml
mcp:
  context7:
    api_key: "..."
  confluence_mcp:
    CONFLUENCE_URL: "https://confluence.shopee.io"
    CONFLUENCE_PERSONAL_TOKEN: "..."
    CONFLUENCE_AUTH_TYPE: "pat"
  weather_mcp:
    QWEATHER_API_KEY: "..."
    QWEATHER_BASE_URL: "..."
    QWEATHER_TIMEOUT: 10
  tavily_mcp:
    TAVILY_API_KEY: "..."
  # 若将来增加：
  # tavily_mcp:
  #   cache_config:
  #     cache_enabled: true
  #     cache_dir: "./data/mcp_cache"
  #     ...
```

---

## 二、存在的问题

### 2.1 `cache_config` 无法从 Nacos 传递到各 MCP

- `inject_mcp_env_vars` 显式**跳过** `cache_config`，只注入简单标量；`cache_config` 是嵌套模型，没有做展平注入。
- 各 MCP 的 `config.py` 中 `cache_config` 使用 `default_factory=MCPCacheConfig`，即**永远用 schemas 默认值**，无法从 Nacos 的 `mcp.xxx_mcp.cache_config` 读取。
- 即便 Nacos 里配置了 `mcp.tavily_mcp.cache_config: { cache_enabled: true, ... }`，主 `settings.mcp.tavily_mcp.cache_config` 能拿到，但各 MCP 的 `config = Settings()` 仍只用 `MCPCacheConfig()` 默认值。

### 2.2 配置两处定义，易不一致

- **app/schemas/config.py**：`TavilyMCPConfig`、`ConfluenceMCPConfig`、`WeatherMCPConfig` 等，与 Nacos 结构一一对应。
- **各 MCP 的 config.py**：各自的 `Settings` 再次定义 `TAVILY_API_KEY`、`cache_config` 等，与 schemas 重复；字段增减、校验、默认值需维护两份，容易遗漏。

### 2.3 强依赖注入顺序，易在重构时踩坑

- 必须在 `inject_mcp_env_vars(settings.mcp)` **之后**再 `import` 各 MCP server，否则 `config = Settings()` 时环境变量里还没有 Nacos 下发的值。
- `mcp_client` 中已通过注释和 `# fmt: off` 固定顺序，但依赖隐式、脆弱，新人或重构容易破坏。

### 2.4 `inject_mcp_env_vars` 的 MCP 列表与 Nacos 不全对应

- 只处理 `tavily_mcp`、`weather_mcp`、`confluence_mcp`；`ip_locator_mcp`、`time_mcp`、`code_exec_mcp` 未放入。
- 当前这些 MCP 的 schemas 只有 `cache_config`，而 `cache_config` 被跳过，不注入暂无影响；但若以后在 Nacos 为它们增加字段，容易忘记同步到 `inject_mcp_env_vars`。

### 2.5 `code_exec_mcp` 的 schemas 与实现不一致

- **app/schemas/config.CodeExecMCPConfig**：仅含 `cache_config`。
- **code_exec_mcp/config.py 的 CodeExecConfig**：除 `cache_config` 外还有 `EXECUTION_TIMEOUT`、`CPU_TIME_LIMIT`、`MEMORY_LIMIT_MB`、`ALLOWED_IMPORTS` 等。
- 这些沙箱参数**无法通过 Nacos 的 `mcp.code_exec_mcp` 配置**，只能走各 MCP 目录的 `.env` 或系统环境变量，与「Nacos 统一管理 MCP」的目标不一致。

### 2.6 类名 `Settings` 重复

- 各 MCP 的 `config.py` 均使用 `class Settings`，与 `app/core/config.Settings` 重名，在全局搜索、理解依赖时易混淆。

---

## 三、优化方向与建议

### 3.1 主应用内：MCP 直接使用 `settings.mcp.xxx_mcp`（推荐）

**思路**：在主应用内，各 MCP server 不再通过「env 注入 + 各 MCP 的 `config.Settings()`」间接拿配置，而是**直接使用** `settings.mcp.tavily_mcp`、`settings.mcp.confluence_mcp` 等（即 `app/schemas/config` 中的 `XxxMCPConfig`）。

**好处**：

1. **`cache_config` 自然打通**：Nacos 中 `mcp.xxx_mcp.cache_config` 经主 `Settings` 解析后，直接在 `settings.mcp.xxx_mcp.cache_config` 可用，无需再注入或在各 MCP 的 `Settings` 中重写。
2. **配置单一来源**：schemas 与 Nacos 结构一一对应，各 MCP 的 `config.py` 只保留「独立运行」时的 fallback，避免重复定义。
3. **不再依赖 `inject_mcp_env_vars` 与导入顺序**：主应用路径下可移除或收缩 `inject_mcp_env_vars`，导入顺序不再敏感。

**实现要点**：

- 各 MCP 的 `server` 在模块顶层，根据**是否已加载主应用 `app.core.config`** 选择配置来源：
  - 若 `"app.core.config" in sys.modules`（说明主应用已启动，`mcp_client` 已先 `import app.core.config`）：  
    `config = settings.mcp.tavily_mcp`（或对应 `xxx_mcp`）。
  - 否则（独立运行 `python -m app.mcp.mcp_servers.tavily_mcp.server`）：  
    `from .config import config`，从各 MCP 的 `Settings()` 读 `.env` / 环境变量，**不** import `app.core.config`，避免在无 Nacos 时触发主 `Settings()` 校验失败。
- 若某 MCP 的子模块（如 `utils`）也 `from .config import config` 并使用 `config`，须采用相同 if/else，否则在主应用内会触发 `.config` 的 `Settings()` 而缺少 env 报错（已对 `weather_mcp/utils.py` 做同样改造）。

这样：

- **主应用**：`config` 来自 `settings.mcp.xxx_mcp`，包含 Nacos 下发的 `cache_config` 及全部字段。
- **独立运行**：`config` 来自 `.config`，仅依赖本地 `.env` / 环境变量，不依赖 Nacos。

### 3.2 各 MCP 的 `config.py` 仅作「独立运行」fallback

- 主应用路径下不再通过各 MCP 的 `config.Settings()` 读 Nacos 来的值；`config.py` 只服务于**独立运行**：从 `env_file` + 环境变量读取 `TAVILY_API_KEY`、`cache_config` 等（若要从 env 支持 `cache_config`，可对 `MCPCacheConfig` 做 `env_nested_delimiter` 或单独展平键，但独立运行通常用默认 `cache_config` 即可）。
- 类名可改为 `TavilyMCPLocalConfig` 或 `TavilyStandaloneConfig`，避免与 `app.core.config.Settings` 混淆。

### 3.3 收缩或移除 `inject_mcp_env_vars`

- 若主应用内 MCP 全部改为使用 `settings.mcp.xxx_mcp`，则不再需要把 `mcp.*` 注入到 `os.environ`，`inject_mcp_env_vars` 可删除或仅保留给少数仍依赖「仅 env」的独立脚本使用。
- `mcp_client` 中可去掉 `inject_mcp_env_vars(settings.mcp)` 以及与之强绑定的 import 顺序约束。

### 3.4 `code_exec_mcp`：补齐 schemas 与 Nacos

- 在 `app/schemas/config.CodeExecMCPConfig` 中补齐与 `code_exec_mcp/config.CodeExecConfig` 一致的沙箱字段（如 `EXECUTION_TIMEOUT`、`CPU_TIME_LIMIT`、`MEMORY_LIMIT_MB`、`ALLOWED_IMPORTS` 等），并在 Nacos 的 `mcp.code_exec_mcp` 中预留对应结构，便于统一管理和权限控制；`code_exec_mcp` 的 `config` 也可按 3.1 / 3.2 统一为「主应用用 `settings.mcp.code_exec_mcp`，独立运行用本地 `config`」。

### 3.5 `inject_mcp_env_vars` 的 MCP 列表（若暂时保留）

- 若短期内仍保留 `inject_mcp_env_vars`（例如给独立进程或未改造的 MCP 用），建议在注释中明确：  
  - 哪些 MCP 依赖注入（tavily / weather / confluence）；  
  - 哪些仅含 `cache_config` 且被跳过（ip_locator / time / code_exec 等）；  
  - 今后在 Nacos 为这些 MCP 增加新字段时，须同步考虑注入或改为 3.1 的「直接使用 `settings.mcp`」。

---

## 四、实施顺序建议

1. **先做 3.1 + 3.2**：对 `tavily_mcp`、`confluence_mcp`、`weather_mcp` 改为「主应用用 `settings.mcp.xxx_mcp`，独立运行用 `.config`」，并收缩 `inject_mcp_env_vars` 或移除对上述三者的注入，验证 Nacos 中 `mcp.xxx_mcp.cache_config` 生效。
2. **再做 3.4**：统一 `code_exec_mcp` 的 schemas 与 Nacos，并接入 `settings.mcp.code_exec_mcp`。
3. **最后**：对 `ip_locator_mcp`、`time_mcp` 等仅 `cache_config` 的 MCP，按需统一为 `settings.mcp.xxx_mcp`，并弱化或移除 `inject_mcp_env_vars`。

---

## 五、小结

| 问题 | 影响 | 优化后 |
|------|------|--------|
| `cache_config` 无法从 Nacos 到各 MCP | 缓存开关、目录、TTL 等无法统一配置 | 主应用内直接用 `settings.mcp.xxx_mcp`，`cache_config` 自然可用 |
| 配置在 schemas 与各 MCP `config` 重复 | 维护成本高、易不一致 | 主应用路径以 schemas 为准；各 MCP `config` 仅 fallback |
| 强依赖 `inject_mcp_env_vars` 与 import 顺序 | 重构易出错 | 主应用不再依赖注入与顺序 |
| `code_exec_mcp` schemas 与实现不一致 | 沙箱参数无法走 Nacos | 补齐 schemas 与 Nacos 结构 |
| 类名 `Settings` 重复 | 可读性、检索不友好 | 各 MCP 的 fallback 类可重命名 |

上述调整后，MCP 的 config 实例化会更清晰：**主应用统一走 Nacos → `settings.mcp`；独立运行走各 MCP 的 `.config` + `.env`**，既支持 Nacos 下 `cache_config` 等嵌套配置，又保留独立运行能力。
