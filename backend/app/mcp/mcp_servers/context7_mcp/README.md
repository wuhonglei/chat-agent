# Context7 MCP（代理模式）

通过 FastMCP 代理远程 [Context7](https://context7.com) HTTP MCP 服务，并为 LLM 提供最新文档查询能力。

## 运行方式

- **主应用内**：由 `mcp_client` 以 `FastMCPTransport(proxy)` 进程内调用，配置来自 `settings.mcp.context7`（含 `api_key`）。
- **独立运行**：在目录下配置 `.env` 后执行 `python -m app.mcp.mcp_servers.context7_mcp.test_server` 做连通性测试。

## 配置

### 主应用（Nacos / settings）

```yaml
mcp:
  context7:
    api_key: "your-context7-api-key"
```

### 独立运行（.env）

参考 `.env.example`，必填 `CONTEXT7_API_KEY`；可选 `CONTEXT7_URL`。
