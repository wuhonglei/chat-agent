---
name: weather
description: 查询指定城市的天气信息（模拟数据，用于演示）
version: 1.0.0
author: AI Doc Team
tags: [weather, city, utility]
permissions: []
parameters: {"city": {"type": "string", "description": "城市名称，如 北京、上海"}}
timeout: 10
---

# Weather Skill

查询城市天气。当前为模拟实现，返回固定格式的模拟数据。

## 返回格式

参见 schemas/response.json。
