## Time MCP Server 说明
这个 MCP Server 提供了一个工具，可以获取当前时间。

## 使用方法
```python
from fastmcp import Client
from app.mcp.mcp_servers.time_mcp.server import mcp

client = Client(mcp)
result = await client.call_tool("get_current_time", {})
print(result)
```