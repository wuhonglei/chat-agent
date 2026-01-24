# Context7 MCP（代理模式）

通过 FastMCP 代理远程 [Context7](https://context7.com) HTTP MCP 服务，并为 LLM 提供最新文档查询能力；支持通过 `ResponseCachingMiddleware` 对 `tools/call`、`list_tools` 等做缓存。

## 运行方式

- **主应用内**：由 `mcp_client` 以 `FastMCPTransport(proxy)` 进程内调用，配置来自 `settings.mcp.context7`（含 `api_key`、`cache_config`）。
- **独立运行**：在目录下配置 `.env` 后执行 `python -m app.mcp.mcp_servers.context7_mcp.test_server` 做连通性测试。

## 配置

### 主应用（Nacos / settings）

```yaml
mcp:
  context7:
    api_key: "your-context7-api-key"
    cache_config:
      cache_enabled: true
      cache_dir: "./data/mcp_cache/context7"
      call_tool_ttl: 300
      call_tool_excluded: []
```

### 独立运行（.env）

参考 `.env.example`，必填 `CONTEXT7_API_KEY`；可选 `CONTEXT7_URL`、`CONTEXT7_VERIFY_SSL`、`CONTEXT7_CACHE_ENABLED`、`CONTEXT7_CACHE_DIR`、`CONTEXT7_CALL_TOOL_TTL`。

## 缓存

当 `cache_config.cache_enabled=true` 时，`ResponseCachingMiddleware` 会缓存 `tools/call`、`list_tools` 等结果，减少对 Context7 的重复请求。
