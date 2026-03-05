# 组件工具集成需求文档

## 需求概述

前端在进行 AI 对话时，需要支持将 AI 回复中的某些 JSON 代码块渲染为 React 组件。本需求描述了如何在后端实现组件工具的动态加载、转换和调用机制。

## 功能需求

### 1. 输入数据

- **来源**：前端在 `ChatRequest` 中传递 `component_tool_names` 字段
- **格式**：字符串数组，例如 `['weather']`
- **含义**：表示前端支持将这些组件名称对应的 JSON 代码块渲染为 React 组件
- **位置**：`app/api/chat.py:40-41`

```python
component_tool_names = chat_request.component_tool_names  # 例如: ['weather']
```

### 2. JSON Schema 获取与缓存

#### 2.1 Schema 获取
- **接口地址**：`http://localhost:3000/component-schemas/{component_tool_name}.json`
- **示例**：`http://localhost:3000/component-schemas/weather.json`
- **返回格式**：JSON Schema 格式，定义了组件的 Props 结构

##### 2.1.1 Schema 获取类设计
- **类名**：`ComponentSchemaService`（建议位置：`app/services/component_schema_service.py`）
- **职责**：
  - 封装 Schema 的 HTTP 请求逻辑
  - 管理 Schema 的内存缓存（使用类变量或实例变量）
  - 提供统一的错误处理和重试机制
  - 支持批量获取多个组件的 Schema
- **主要方法**：
  - `get_schema(component_tool_name: str) -> dict`：获取单个组件的 Schema（带缓存检查）
  - `get_schemas(component_tool_names: list[str]) -> dict[str, dict]`：批量获取多个组件的 Schema
  - `_fetch_schema_from_api(component_tool_name: str) -> dict`：从 API 获取 Schema（私有方法）
  - `clear_cache()`：清空缓存（可选，用于测试或强制刷新）
- **缓存策略**：
  - 使用类变量或单例模式，确保缓存在整个应用生命周期内共享
  - 缓存键：`component_tool_name`
  - 缓存值：完整的 JSON Schema 字典
  - 在获取前先检查缓存，缓存命中则直接返回，未命中则请求 API 并更新缓存
- **错误处理**：
  - 处理网络请求失败（超时、连接错误等）
  - 处理 HTTP 错误状态码（404、500 等）
  - 处理 JSON 解析错误
  - 记录详细的错误日志，便于排查问题
- **配置项**：
  - Schema API 基础地址（建议从配置文件读取，默认：`http://localhost:3000/component-schemas/`）
  - 请求超时时间（建议默认 5 秒）
  - 重试次数（建议默认 2 次）

#### 2.2 缓存机制
- **要求**：如果某个组件的 JSON schema 已经获取过，则不再重新请求
- **实现**：由 `ComponentSchemaService` 类统一管理，在内存中存储已获取的 schema，避免重复 HTTP 请求
- **缓存范围**：应用级别的缓存（使用类变量），所有 `ComponentSchemaService` 实例共享同一缓存

#### 2.3 Schema 示例

以 `weather` 组件为例，其 JSON schema 定义如下：

```json
{
  "description": "天气组件 Props",
  "type": "object",
  "properties": {
    "location": {
      "description": "位置信息",
      "type": "string"
    },
    "data": {
      "$ref": "#/definitions/WeatherNowData",
      "description": "天气数据"
    },
    "aqi": {
      "description": "空气质量指数（可选）",
      "type": "object",
      "properties": {
        "level": {
          "description": "空气质量等级",
          "type": "string"
        },
        "category": {
          "description": "空气质量类别",
          "type": "string"
        },
        "aqi": {
          "description": "空气质量指数",
          "type": "string"
        }
      },
      "required": [
        "aqi",
        "category",
        "level"
      ]
    }
  },
  "required": [
    "data",
    "location"
  ],
  "definitions": {
    "WeatherNowData": {
      "description": "和风天气实时天气数据接口\n参考文档: https://dev.qweather.com/docs/api/weather/weather-now/",
      "type": "object",
      "properties": {
        "obsTime": {
          "description": "观测时间",
          "type": "string"
        },
        "temp": {
          "description": "温度",
          "type": "string"
        },
        "feelsLike": {
          "description": "体感温度",
          "type": "string"
        },
        "icon": {
          "description": "天气图标代码",
          "type": "string"
        },
        "text": {
          "description": "天气状况文字描述",
          "type": "string"
        },
        "wind360": {
          "description": "风向360度",
          "type": "string"
        },
        "windDir": {
          "description": "风向",
          "type": "string"
        },
        "windScale": {
          "description": "风力等级",
          "type": "string"
        },
        "windSpeed": {
          "description": "风速",
          "type": "string"
        },
        "humidity": {
          "description": "相对湿度",
          "type": "string"
        },
        "precip": {
          "description": "降水量",
          "type": "string"
        },
        "pressure": {
          "description": "大气压强",
          "type": "string"
        },
        "vis": {
          "description": "能见度",
          "type": "string"
        },
        "cloud": {
          "description": "云量",
          "type": "string"
        },
        "dew": {
          "description": "露点温度",
          "type": "string"
        },
        "tempMin": {
          "description": "最低温度",
          "type": "string"
        },
        "tempMax": {
          "description": "最高温度",
          "type": "string"
        }
      },
      "required": [
        "cloud",
        "dew",
        "feelsLike",
        "humidity",
        "icon",
        "obsTime",
        "precip",
        "pressure",
        "temp",
        "text",
        "vis",
        "wind360",
        "windDir",
        "windScale",
        "windSpeed"
      ]
    }
  },
  "$schema": "http://json-schema.org/draft-07/schema#"
}
```

### 3. 组件工具定义转换

#### 3.1 转换时机
- **触发条件**：在 MCP tools 调用完成后，调用 `_call_llm_with_component_tools` 方法时
- **位置**：`app/services/chat_service.py` 的 `_call_llm_with_component_tools` 方法内部
- **流程**：
  1. 在 `stream_message` 方法中，`_call_llm_with_mcp_tools` 执行完毕后
  2. 调用 `_call_llm_with_component_tools` 方法
  3. 在 `_call_llm_with_component_tools` 内部，获取 schema 并转换为 tool 定义格式

#### 3.2 转换格式
将获取到的 JSON schema 转换为 LLM 可用的 tool 定义格式，格式如下：

```python
{
    "type": "function",
    "function": {
        "name": "generate_component_{component_tool_name}",  # 例如: "generate_component_weather"
        "description": "生成 {component_tool_name} 组件的 props 数据",
        "parameters": {
            "type": "object",
            "properties": {
                # ... schema 中的 properties
            },
            "required": [
                # ... schema 中的 required
            ]
        }
    }
}
```

**说明**：
- `parameters.properties`：从 JSON schema 转换而来，包含组件的 props 定义
- LLM 调用此工具时，返回的数据格式为 `{...}`

#### 3.3 Schema 转换规则
- 工具 `parameters.properties`：从 JSON schema 转换而来
- 处理 `$ref` 引用（如 `#/definitions/WeatherNowData`），需要展开定义
- 保留 `description` 字段，用于 LLM 理解工具用途
- `parameters.required` 必须包含 `[...]`

### 4. LLM 工具调用流程

#### 4.1 工具提供
- 在 MCP tools 调用完成后，将转换后的组件工具定义添加到 tools 列表中
- 使用 `_call_llm_with_component_tools` 方法进行后续调用
  - **方法位置**：`app/services/chat_service.py` 的 `_call_llm_with_component_tools` 方法
  - **调用时机**：在 `stream_message` 方法中，MCP tools 调用完成后（`_call_llm_with_mcp_tools` 执行完毕）
  - **输入参数**：
    - `messages`: 包含 system message、user message 和 MCP tool call messages 的消息列表
    - `model`: LLM 模型名称
    - `component_tool_names`: 组件工具名称列表（例如：`['weather']`）
  - **功能**：
    - 获取并转换组件工具的 JSON schema 为 LLM tool 定义格式
    - 将组件工具添加到 tools 列表
    - 调用 LLM API，让 LLM 决定是否调用组件工具
    - 收集组件工具调用的结果，存储到 `self.collected_component_data` 中
  - **返回**：异步生成器，yield 工具调用相关的消息（`ToolMessage`）

#### 4.2 工具调用
- LLM 根据上下文和用户需求，决定是否调用组件工具
- 调用时，LLM 需要返回格式为 json schema 填充后的数据
- 工具名称格式：`generate_component_{component_tool_name}`（例如：`generate_component_weather`）

#### 4.3 调用结果
- 工具调用返回的数据格式如下：
  ```json
  {
      // json schema 填充后的数据，符合组件 JSON schema 定义的 properties
      "location": "北京市",
      "data": {
        "obsTime": "2025-12-07T12:00:00+08:00",
        "temp": "20",
        // ... 其他 WeatherNowData 字段
      },
      "aqi": {
        // ... 可选字段
      }
  }
  ```
- 需要收集所有组件工具调用的结果

### 5. 数据拼接

#### 5.1 数据收集
- 收集所有组件工具调用返回的数据
- 存储格式：列表，每个元素为工具调用返回的完整数据对象
  ```python
  [
    {
      "location": "北京市",
      "data": { ... },
      "aqi": { ... }
    },
    // ... 其他组件数据
  ]
  ```

#### 5.2 Prompt 拼接
- 将所有收集到的组件数据拼接到最终的 `user_prompt` 中
- 拼接位置：在 `app/services/chat_service.py` 的 `stream_message` 方法中，调用 `_stream_final_response` 之前
- 拼接方式：将组件数据以结构化格式添加到 user_message 中，供 LLM 生成最终回复
- 数据格式：保持 `{...}` 结构，便于前端识别和渲染

## 实现要点

### 1. 缓存机制
- **位置**：在 `ComponentSchemaService` 类中管理缓存（使用类变量实现单例缓存）
- **存储**：使用字典存储 `{component_tool_name: json_schema}`
- **检查**：在 `ComponentSchemaService.get_schema()` 方法中，获取 schema 前先检查缓存
- **使用**：在 `ChatService` 中通过 `ComponentSchemaService` 实例获取 schema，无需直接管理缓存

### 2. Schema 转换
- **函数**：创建独立的函数处理 JSON schema 到 LLM tool 格式的转换
- **$ref 处理**：需要递归处理 schema 中的 `$ref` 引用，展开 `definitions` 中的定义
- **工具命名**：统一使用 `generate_component_{component_tool_name}` 格式

### 3. 时机控制
- **MCP tools 调用**：在 `_call_llm_with_mcp_tools` 方法中完成
- **组件工具调用**：在 MCP tools 调用完成后，使用 `_call_llm_with_component_tools` 方法进行组件工具的调用
  - 在 `stream_message` 方法中，`_call_llm_with_mcp_tools` 执行完毕后调用
  - `_call_llm_with_component_tools` 内部会获取 schema、转换格式、调用 LLM 并收集结果
- **最终回复生成**：在 `_stream_final_response` 调用前，将组件工具调用的结果拼接到 user_prompt

### 4. 数据收集
- **收集位置**：在 `_call_llm_with_component_tools` 方法中，识别组件工具调用并收集结果
  - 当 LLM 调用组件工具（`generate_component_{component_tool_name}`）时，从工具调用的 arguments 中提取 `data` 字段
  - 将提取的数据存储到 `self.collected_component_data` 列表中
- **存储位置**：在 `ChatService` 实例中存储收集到的组件数据（`self.collected_component_data`）
- **数据格式**：使用列表存储，每个元素为工具调用返回的完整数据对象（符合 JSON schema 的 props 数据）
  ```python
  [
    {
      "location": "北京市",
      "data": { ... },
      "aqi": { ... }
    }
  ]
  ```

### 5. Prompt 拼接
- **拼接函数**：在 `app/prompts/prompt.py` 中创建或修改相关函数
- **拼接格式**：将组件数据以清晰的格式添加到 user_message 中
- **示例格式**：
  ```
  用户消息: {original_user_message}

  组件数据:
  [
    {
      "location": "北京市",
      "data": { ... },
      "aqi": { ... }
    }
  ]
  ```

## 代码位置

### 主要文件
- **入口**：`app/api/chat.py:40-41`（获取 `component_tool_names`）
- **主要逻辑**：`app/services/chat_service.py`
  - `stream_message`：主流程控制
  - `_call_llm_with_mcp_tools`：MCP 工具调用处理
  - `_call_llm_with_component_tools`：组件工具调用处理（在 MCP tools 调用完成后执行）
  - `_stream_final_response`：最终回复生成
- **Prompt 处理**：`app/prompts/prompt.py`
  - `get_user_message_for_component_render`：用户消息处理

### 需要修改/新增的文件
1. **新增**：`app/services/component_schema_service.py`：Schema 获取服务类（封装 HTTP 请求和缓存逻辑）
2. `app/services/chat_service.py`：添加组件工具处理逻辑，使用 `ComponentSchemaService` 获取 Schema
3. `app/prompts/prompt.py`：修改或新增 prompt 拼接函数
4. 可能需要新增：`app/utils/component_tools.py`：组件工具相关的工具函数（如 Schema 转换函数）

## 实现流程

```
1. 接收 component_tool_names
   ↓
2. 执行 MCP tools 调用（通过 _call_llm_with_mcp_tools）
   ↓
3. 调用 _call_llm_with_component_tools 方法：
   - 使用 ComponentSchemaService 获取并缓存 JSON schemas（如果未缓存）
   - 将 JSON schemas 转换为 LLM tool 定义（使用 convert_schema_to_tool_definition）
   - 添加组件工具到 tools 列表
   - 调用 LLM API，让 LLM 决定是否调用组件工具
   - 收集所有组件工具调用返回的数据（格式：json schema 填充后的数据）
   ↓
4. 将收集到的组件数据拼接到 user_prompt（使用 get_user_message_with_component_data）
   ↓
5. 生成最终回复（通过 _stream_final_response）
```

## 注意事项

1. **错误处理**：需要处理 JSON schema 获取失败、转换失败等情况
2. **性能优化**：缓存机制避免重复请求，提高性能
3. **$ref 处理**：确保正确处理 JSON schema 中的 `$ref` 引用
4. **工具命名冲突**：确保组件工具名称不与 MCP tools 名称冲突
5. **数据格式**：确保 prop data 符合前端 React 组件的预期格式

## 测试要点

1. **ComponentSchemaService 测试**：
   - 测试单个 Schema 获取（`get_schema`）
   - 测试批量 Schema 获取（`get_schemas`）
   - 测试缓存机制（首次请求后，第二次应从缓存获取）
   - 测试错误处理（网络错误、HTTP 错误、JSON 解析错误等）
   - 测试缓存清理（`clear_cache`）
2. 测试 Schema 到 tool 定义的转换
3. 测试组件工具的调用流程
4. 测试 prop data 的收集和拼接
5. 测试多个组件工具同时使用的情况
6. 测试错误场景（schema 获取失败、转换失败等）
