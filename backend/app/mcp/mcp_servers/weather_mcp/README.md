# 和风天气 MCP Server 使用说明

## 概述

这是一个基于和风天气 API 的 MCP (Model Context Protocol) Server，提供天气查询服务。

官方文档：https://dev.qweather.com/docs/start/

## 文件结构

- `server.py` - MCP Server 实现，提供天气查询工具
- `config.py` - 配置模块，使用 Pydantic Settings 管理环境变量

## 环境配置

### 1. 获取 API Key

1. 访问 [和风天气开发者平台](https://dev.qweather.com/)
2. 注册账号并创建应用
3. 获取 API Key（免费版或付费版）

### 2. 配置环境变量

创建 `.env` 文件或设置系统环境变量：

```bash
# 必需配置
QWEATHER_API_KEY=your_api_key_here
QWEATHER_BASE_URL=https://devapi.qweather.com

# 可选配置
QWEATHER_TIMEOUT=10
```

**重要提示**：
- `QWEATHER_API_KEY` 和 `QWEATHER_BASE_URL` 是必需的，缺少任一项会导致程序启动失败
- 配置通过 Pydantic Settings 加载，优先使用环境变量，其次使用 `.env` 文件
- `QWEATHER_BASE_URL` 必须以 `http://` 或 `https://` 开头

## 使用方法

### 启动 MCP Server

Server 支持两种传输模式：

#### 1. HTTP 模式（默认）

```bash
python server.py --transport http --port 8001
```

Server 将在 `http://localhost:8001` 启动 HTTP 服务。

#### 2. Stdio 模式

```bash
python server.py --transport stdio
```

Server 将通过标准输入输出与 MCP 客户端通信，适用于集成到其他应用中。

### 命令行参数

- `--transport`: 传输方式，可选 `http` 或 `stdio`（默认：`http`）
- `--port`: HTTP 模式下的端口号（默认：`8001`）

## 可用的工具（Tools）

Server 提供以下 5 个 MCP 工具：

### 1. search_city - 搜索城市位置信息

根据城市名称或坐标搜索城市信息，获取 LocationID。

**参数：**
- `location` (必需): 城市名称、经纬度坐标、LocationID 或 Adcode
  - 示例：`"北京"` 或 `"116.41,39.92"`
- `adm` (可选): 上级行政区划，用于过滤重名城市
  - 默认值：`""`
- `range` (可选): 搜索范围（ISO 3166 国家代码）
  - 默认值：`"cn"`
- `number` (可选): 返回结果数量（1-20）
  - 默认值：`3`
- `lang` (可选): 语言设置
  - 默认值：`"zh"`

**示例：**
```python
{
    "location": "北京",
    "range": "cn",
    "number": 3,
    "lang": "zh"
}
```

### 2. get_current_weather - 获取实时天气

获取指定位置的实时天气信息。

**参数：**
- `location` (必需): LocationID 或经纬度坐标
  - 示例：`"101010100"` 或 `"116.41,39.92"`
- `lang` (可选): 语言设置
  - 默认值：`"zh"`
- `unit` (可选): 单位设置（`m`=公制，`i`=英制）
  - 默认值：`"m"`

**示例：**
```python
{
    "location": "101010100",
    "lang": "zh",
    "unit": "m"
}
```

### 3. get_weather_forecast - 获取天气预报

获取指定位置的天气预报信息。

**参数：**
- `location` (必需): LocationID 或经纬度坐标
- `days` (可选): 预报天数，支持 `3d`、`7d`、`10d`、`15d`、`30d`
  - 默认值：`"7d"`
- `lang` (可选): 语言设置
  - 默认值：`"zh"`
- `unit` (可选): 单位设置
  - 默认值：`"m"`

**示例：**
```python
{
    "location": "101010100",
    "days": "7d",
    "lang": "zh",
    "unit": "m"
}
```

### 4. get_weather_alerts - 获取天气预警

获取指定位置的天气灾害预警信息。

**参数：**
- `location` (必需): LocationID 或经纬度坐标
- `lang` (可选): 语言设置
  - 默认值：`"zh"`

**示例：**
```python
{
    "location": "101010100",
    "lang": "zh"
}
```

### 5. get_air_quality - 获取空气质量

获取指定位置的实时空气质量信息。

**参数：**
- `location` (必需): LocationID 或经纬度坐标
- `lang` (可选): 语言设置
  - 默认值：`"zh"`

**示例：**
```python
{
    "location": "101010100",
    "lang": "zh"
}
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

## 技术特性

### 配置管理
- 使用 **Pydantic Settings** 进行配置管理
- 支持从环境变量和 `.env` 文件加载配置
- 启动时自动验证必需配置项
- 自动验证 `QWEATHER_BASE_URL` 格式

### 错误处理
- 所有工具都有统一的异常处理机制
- API 请求失败会返回友好的错误信息
- HTTP 超时设置可配置（默认 10 秒）

### 数据模型
- 使用 Pydantic 定义严格的数据模型
- 支持类型提示和自动验证
- 模型包括：`WeatherNow`、`WeatherDaily`、`WeatherResponse`

## 常见问题

### 1. 程序启动失败：ValidationError

**原因**：缺少必需的环境变量 `QWEATHER_API_KEY` 或 `QWEATHER_BASE_URL`

**解决方案**：
- 确保设置了所有必需的环境变量
- 检查 `.env` 文件是否在正确的目录下
- 验证环境变量值格式是否正确

### 2. API 请求失败

**可能原因**：
- API Key 无效或已过期
- 网络连接问题
- 请求超出 API 配额限制

**解决方案**：
- 检查 API Key 是否有效
- 确认网络连接正常
- 查看和风天气控制台的 API 调用配额

### 3. LocationID 不正确

**解决方案**：
- 先使用 `search_city` 工具搜索城市
- 从返回结果中获取正确的 LocationID
- LocationID 通常是 9 位数字（如：`101010100`）

### 4. QWEATHER_BASE_URL 格式错误

**错误信息**：`QWEATHER_BASE_URL 必须以 http:// 或 https:// 开头`

**解决方案**：
- 确保 URL 以 `http://` 或 `https://` 开头
- 开发环境使用：`https://devapi.qweather.com`
- 生产环境使用：`https://api.qweather.com`

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
