# 和风天气 MCP Server 使用说明

## 概述

这是一个基于和风天气 API 的 MCP (Model Context Protocol) Server，提供天气查询服务。

## 文件结构

- `weather_server.py` - MCP Server 实现，提供天气查询工具
- `weather_client.py` - MCP Client 实现，用于调用 Server 的工具
- `config.py` - 配置文件，管理环境变量
- `test_weather.py` - 直接测试天气 API 功能的脚本

## 环境配置

### 1. 设置环境变量

创建 `.env` 文件或设置环境变量：

```bash
# 和风天气 API 配置
QWEATHER_API_KEY=your_api_key_here
QWEATHER_BASE_URL=https://devapi.qweather.com
QWEATHER_TIMEOUT=10
```

### 2. 获取 API Key

1. 访问 [和风天气开发者平台](https://dev.qweather.com/)
2. 注册账号并创建应用
3. 获取 API Key

## 使用方法

### 方法一：使用 MCP Client/Server 模式

#### 1. 启动 MCP Server

```bash
cd tests/mcp_demo/weather_mcp
python weather_server.py
```

Server 将在 `http://localhost:8000/mcp` 启动。

#### 2. 运行 MCP Client

```bash
python weather_client.py
```

### 方法二：直接测试 API 功能

```bash
python test_weather.py
```

## 可用的工具

### 1. search_city - 搜索城市位置信息

```python
result = await client.call_tool("search_city", {
    "location": "北京",
    "adm": "",
    "range": "cn",
    "number": 10,
    "lang": "zh"
})
```

### 2. get_current_weather - 获取实时天气

```python
result = await client.call_tool("get_current_weather", {
    "location": "101010100",  # 北京的 LocationID
    "lang": "zh",
    "unit": "m"
})
```

### 3. get_weather_forecast - 获取天气预报

```python
result = await client.call_tool("get_weather_forecast", {
    "location": "101010100",
    "days": "7d",  # 支持 3d, 7d, 10d, 15d, 30d
    "lang": "zh",
    "unit": "m"
})
```

### 4. get_weather_alerts - 获取天气预警

```python
result = await client.call_tool("get_weather_alerts", {
    "location": "101010100",
    "lang": "zh"
})
```

### 5. get_air_quality - 获取空气质量

```python
result = await client.call_tool("get_air_quality", {
    "location": "101010100",
    "lang": "zh"
})
```

## 参数说明

### location 参数
- 可以是 LocationID（如：101010100）
- 也可以是经纬度坐标（如：116.41,39.92）

### lang 参数
- `zh` - 中文（默认）
- `en` - 英文

### unit 参数
- `m` - 公制单位（默认）
- `i` - 英制单位

### days 参数（仅天气预报）
- `3d` - 3天预报
- `7d` - 7天预报（默认）
- `10d` - 10天预报
- `15d` - 15天预报
- `30d` - 30天预报

## 常见问题

### 1. API Key 错误
确保设置了正确的 `QWEATHER_API_KEY` 环境变量。

### 2. 网络连接问题
检查网络连接和防火墙设置。

### 3. 服务器未启动
确保 MCP Server 正在运行在 `http://localhost:8000/mcp`。

### 4. 位置 ID 不正确
可以使用 `search_city` 工具先搜索城市获取正确的 LocationID。

## 示例输出

```json
{
  "code": "200",
  "updateTime": "2024-01-01T12:00+08:00",
  "fxLink": "http://hfx.link/1abc",
  "now": {
    "obsTime": "2024-01-01T12:00+08:00",
    "temp": "15",
    "feelsLike": "13",
    "icon": "100",
    "text": "晴",
    "wind360": "0",
    "windDir": "北风",
    "windScale": "1",
    "windSpeed": "3",
    "humidity": "65",
    "precip": "0.0",
    "pressure": "1020",
    "vis": "16",
    "cloud": "10",
    "dew": "8"
  },
  "refer": {
    "sources": ["Weather China"],
    "license": ["Commercial license"]
  }
}
```