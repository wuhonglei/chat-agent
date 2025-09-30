# 和风天气 MCP Server

基于和风天气 API 的 Model Context Protocol (MCP) 服务器，提供丰富的天气查询功能。

## 功能特性

- 🌤️ **实时天气查询** - 获取当前天气状况
- 📅 **天气预报** - 支持 3天、7天、10天、15天、30天预报
- 🏙️ **城市搜索** - 根据城市名称搜索位置信息
- ⚠️ **天气预警** - 获取天气预警信息
- 🌬️ **空气质量** - 查询空气质量数据
- 🌍 **多语言支持** - 支持中文、英文等多种语言
- 📏 **单位选择** - 支持公制和英制单位

## 安装和配置

### 1. 安装依赖

确保已安装 `fastmcp` 和 `httpx`：

```bash
pip install fastmcp httpx
```

### 2. 获取 API Key

1. 访问 [和风天气开发平台](https://dev.qweather.com/)
2. 注册账号并创建项目
3. 获取 API Key

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填入您的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
QWEATHER_API_KEY=your_api_key_here
QWEATHER_BASE_URL=https://devapi.qweather.com
QWEATHER_TIMEOUT=10
```

### 4. 运行服务器

```bash
python weather.py
```

## API 工具说明

### 1. get_current_weather - 获取实时天气

获取指定位置的实时天气信息。

**参数：**
- `location` (必填): 位置信息，可以是 LocationID（如：101010100）或经纬度坐标（如：116.41,39.92）
- `lang` (可选): 多语言设置，支持 zh（中文）、en（英文）等，默认为 zh
- `unit` (可选): 单位设置，m（公制）或 i（英制），默认为 m

**示例：**
```python
# 使用 LocationID 查询北京天气
result = await get_current_weather(location="101010100")

# 使用经纬度查询上海天气
result = await get_current_weather(location="121.47,31.23")

# 使用英文和英制单位
result = await get_current_weather(
    location="101010100", 
    lang="en", 
    unit="i"
)
```

### 2. get_weather_forecast - 获取天气预报

获取指定位置的天气预报信息。

**参数：**
- `location` (必填): 位置信息
- `days` (可选): 预报天数，支持 3d、7d、10d、15d、30d，默认为 7d
- `lang` (可选): 多语言设置，默认为 zh
- `unit` (可选): 单位设置，默认为 m

**示例：**
```python
# 获取7天天气预报
result = await get_weather_forecast(location="101010100", days="7d")

# 获取15天天气预报
result = await get_weather_forecast(location="101010100", days="15d")
```

### 3. search_city - 搜索城市

根据城市名称搜索位置信息。

**参数：**
- `location` (必填): 城市名称，如：北京、上海、广州等
- `adm` (可选): 行政区划，如：北京、上海、广东等
- `range` (可选): 搜索范围，cn（中国）、world（全球），默认为 cn
- `number` (可选): 返回结果数量，最多20个，默认为 10
- `lang` (可选): 多语言设置，默认为 zh

**示例：**
```python
# 搜索北京
result = await search_city(location="北京")

# 搜索上海，限制在上海市范围内
result = await search_city(location="上海", adm="上海")

# 搜索全球的 London
result = await search_city(location="London", range="world")
```

### 4. get_weather_alerts - 获取天气预警

获取指定位置的天气预警信息。

**参数：**
- `location` (必填): 位置信息
- `lang` (可选): 多语言设置，默认为 zh

**示例：**
```python
result = await get_weather_alerts(location="101010100")
```

### 5. get_air_quality - 获取空气质量

获取指定位置的空气质量信息。

**参数：**
- `location` (必填): 位置信息
- `lang` (可选): 多语言设置，默认为 zh

**示例：**
```python
result = await get_air_quality(location="101010100")
```

## 数据字段说明

### 实时天气数据 (WeatherNow)

| 字段 | 类型 | 说明 |
|------|------|------|
| obsTime | str | 观测时间 |
| temp | str | 温度 |
| feelsLike | str | 体感温度 |
| icon | str | 天气图标代码 |
| text | str | 天气状况文字描述 |
| wind360 | str | 风向360度 |
| windDir | str | 风向 |
| windScale | str | 风力等级 |
| windSpeed | str | 风速 |
| humidity | str | 相对湿度 |
| precip | str | 降水量 |
| pressure | str | 大气压强 |
| vis | str | 能见度 |
| cloud | str | 云量 |
| dew | str | 露点温度 |

### 天气预报数据 (WeatherDaily)

| 字段 | 类型 | 说明 |
|------|------|------|
| fxDate | str | 预报日期 |
| sunrise | str | 日出时间 |
| sunset | str | 日落时间 |
| moonrise | str | 月出时间 |
| moonset | str | 月落时间 |
| moonPhase | str | 月相 |
| moonPhaseIcon | str | 月相图标 |
| tempMax | str | 最高温度 |
| tempMin | str | 最低温度 |
| iconDay | str | 白天天气图标 |
| textDay | str | 白天天气状况 |
| iconNight | str | 夜间天气图标 |
| textNight | str | 夜间天气状况 |
| wind360Day | str | 白天风向360度 |
| windDirDay | str | 白天风向 |
| windScaleDay | str | 白天风力等级 |
| windSpeedDay | str | 白天风速 |
| wind360Night | str | 夜间风向360度 |
| windDirNight | str | 夜间风向 |
| windScaleNight | str | 夜间风力等级 |
| windSpeedNight | str | 夜间风速 |
| precip | str | 降水量 |
| uvIndex | str | 紫外线指数 |
| humidity | str | 相对湿度 |
| pressure | str | 大气压强 |
| vis | str | 能见度 |
| cloud | str | 云量 |

## 错误处理

所有 API 调用都会返回统一的响应格式：

**成功响应：**
```json
{
  "code": "200",
  "updateTime": "2024-02-08T13:39+08:00",
  "fxLink": "https://www.qweather.com/weather/beijing-101010100.html",
  "now": { ... },
  "refer": { ... }
}
```

**错误响应：**
```json
{
  "error": "错误描述信息"
}
```

## 注意事项

1. **API Key 配置**: 必须设置 `QWEATHER_API_KEY` 环境变量
2. **API Base URL 配置**: 必须设置 `QWEATHER_BASE_URL` 环境变量
3. **请求超时时间配置**: 必须设置 `QWEATHER_TIMEOUT` 环境变量
3. **请求限制**: 注意和风天气 API 的调用频率限制
4. **数据延迟**: 实况数据有 5-20 分钟延迟
5. **免费额度**: 对非商业用户完全免费
6. **LocationID**: 建议使用 LocationID 而不是经纬度坐标，查询更准确

## 相关链接

- [和风天气开发平台](https://dev.qweather.com/)
- [和风天气 API 文档](https://dev.qweather.com/docs/api/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)

