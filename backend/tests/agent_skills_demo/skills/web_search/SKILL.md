---
name: web_search
description: 联网搜索，支持通过 DuckDuckGo 等 API 获取实时信息
---

# 联网搜索

## 何时使用

当用户需要查询实时信息、最新新闻、网络资料时使用本技能。

## 使用方式

### 方式一：execute_shell_command 配合 curl

```bash
curl -s "https://api.duckduckgo.com/?q=查询关键词&format=json"
```

### 方式二：execute_python_code 配合 urllib

```python
import urllib.request
import json
query = "Python 3.13 新特性"
url = f"https://api.duckduckgo.com/?q={query}&format=json"
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read().decode())
    # 提取 Abstract 或 RelatedTopics
    result = data.get("Abstract", data.get("RelatedTopics", []))
print(result)
```

## 注意事项

- DuckDuckGo Instant Answer API 无需 API Key
- 响应为 JSON，需解析后提取有用信息
- 若需更强大搜索，可接入 Tavily、Google Custom Search 等
