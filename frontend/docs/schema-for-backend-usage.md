# JSON Schema 用于后端 MCP 工具参数填充分析

## 问题

生成的 JSON Schema 能否被后端用于 MCP 工具参数 prop data 的填充？

## 分析

### 1. 生成的 JSON Schema 格式

当前生成的 JSON Schema 使用标准的 **JSON Schema Draft 7** 格式，包含：

- ✅ 基本类型定义（string, number, boolean, object）
- ✅ 嵌套对象结构
- ✅ `$ref` 引用（用于类型复用）
- ✅ `definitions` 部分（存放被引用的类型定义）
- ✅ `required` 字段（必填属性）
- ✅ `description` 字段（字段描述，来自 TypeScript JSDoc 注释）

### 2. 后端使用场景

后端收到组件工具的 JSON Schema 后，可以用于：

#### 场景 A：指导 LLM 生成组件数据

后端可以使用这个 schema 来指导 LLM（如 GPT、Claude 等）生成符合组件要求的 prop data：

```python
# 伪代码示例
component_schema = {
    "type": "object",
    "properties": {
        "location": {"type": "string", "description": "位置信息"},
        "data": {"$ref": "#/definitions/WeatherNowData"},
        ...
    },
    "required": ["location", "data"],
    "definitions": {
        "WeatherNowData": {...}
    }
}

# 将 schema 传递给 LLM，要求生成符合该 schema 的数据
llm_response = llm.generate(
    prompt="根据 MCP 工具返回的天气数据，生成符合以下 schema 的组件 props",
    schema=component_schema
)
```

#### 场景 B：数据验证

后端可以使用 JSON Schema 验证库来验证生成的数据是否符合组件要求：

```python
import jsonschema

# 验证生成的数据
jsonschema.validate(instance=generated_props, schema=component_schema)
```

### 3. 潜在问题和解决方案

#### 问题 1：$ref 引用解析

**问题**：生成的 schema 使用了 `$ref` 引用（如 `"$ref": "#/definitions/WeatherNowData"`），某些库可能需要先解析这些引用。

**解决方案**：

**方案 A：使用支持 $ref 的库**（推荐）
- Python: `jsonschema` 库原生支持 `$ref`
- JavaScript: `ajv` 库支持 `$ref`
- 这些库会自动解析 `definitions` 中的引用

**方案 B：手动解析 $ref**
如果使用的库不支持 `$ref`，可以在发送给后端前解析：

```typescript
// 前端：解析 $ref 引用
import { dereference } from 'json-schema-deref-sync';

const resolvedSchema = dereference(componentSchema);
// 发送 resolvedSchema 给后端
```

**方案 C：生成时展开 $ref**
修改生成脚本，生成时直接展开所有 `$ref` 引用（不推荐，会增大文件体积）。

#### 问题 2：Schema 格式兼容性

**检查项**：
- ✅ 使用标准的 JSON Schema Draft 7 格式
- ✅ 包含 `$schema` 字段：`"$schema": "http://json-schema.org/draft-07/schema#"`
- ✅ 所有类型都是 JSON Schema 支持的类型

**结论**：生成的 schema 格式完全兼容标准 JSON Schema，可以直接使用。

### 4. 最佳实践建议

#### 建议 1：保持 $ref 引用（推荐）

**优点**：
- Schema 文件更小
- 类型定义可复用
- 符合 JSON Schema 标准

**使用方式**：
后端使用支持 `$ref` 的库（如 `jsonschema`、`ajv`）即可直接使用。

#### 建议 2：为后端提供两种格式

如果后端需要，可以提供两种格式：

1. **原始格式**（带 $ref）：用于验证和文档
2. **展开格式**（无 $ref）：用于某些不支持 $ref 的场景

```typescript
// 前端工具函数
import { dereference } from 'json-schema-deref-sync';

export function getComponentToolsRequestData(): ComponentToolRequestItem[] {
  return componentTools.map(({ name, schema, when }) => ({
    name,
    schema: schema, // 原始格式（带 $ref）
    schemaResolved: dereference(schema), // 展开格式（可选）
    when,
  }));
}
```

#### 建议 3：添加 Schema 元数据

可以在 schema 中添加一些元数据，帮助后端更好地使用：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WeatherNowProps",
  "description": "天气组件 Props",
  "type": "object",
  ...
}
```

当前生成的 schema 已经包含了 `description` 和 `$schema`，这很好。

### 5. 后端使用示例

#### Python 示例

```python
import jsonschema
import json

# 接收前端传来的 component_tools
component_tools = request.json.get('component_tools', [])

for tool in component_tools:
    tool_name = tool['name']
    tool_schema = tool['schema']
    tool_when = tool['when']

    # 检查是否应该生成该组件
    if should_generate_component(tool_when, mcp_tool_calls):
        # 使用 schema 指导 LLM 生成数据
        props_data = generate_component_props(
            schema=tool_schema,
            mcp_tool_result=mcp_tool_result
        )

        # 验证生成的数据
        try:
            jsonschema.validate(instance=props_data, schema=tool_schema)
            # 数据验证通过，可以返回
        except jsonschema.ValidationError as e:
            # 数据验证失败，记录错误
            logger.error(f"Component {tool_name} props validation failed: {e}")
```

#### JavaScript/TypeScript 示例

```typescript
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true });
addFormats(ajv);

// 接收前端传来的 component_tools
const componentTools = request.body.component_tools || [];

for (const tool of componentTools) {
  const { name, schema, when } = tool;

  // 检查是否应该生成该组件
  if (shouldGenerateComponent(when, mcpToolCalls)) {
    // 编译 schema
    const validate = ajv.compile(schema);

    // 生成组件 props
    const propsData = generateComponentProps(schema, mcpToolResult);

    // 验证生成的数据
    const valid = validate(propsData);
    if (!valid) {
      console.error(`Component ${name} props validation failed:`, validate.errors);
    }
  }
}
```

## 结论

### ✅ 可以直接使用

生成的 JSON Schema **完全适合**用于后端填充 MCP 工具参数 prop data，因为：

1. **标准格式**：使用标准的 JSON Schema Draft 7 格式
2. **完整信息**：包含所有必要的类型定义、必填字段、描述信息
3. **工具支持**：主流 JSON Schema 库（如 `jsonschema`、`ajv`）都支持 `$ref` 引用
4. **LLM 兼容**：可以直接用于指导 LLM 生成符合 schema 的数据

### 📝 注意事项

1. **$ref 解析**：确保后端使用的 JSON Schema 库支持 `$ref`（大多数都支持）
2. **数据验证**：建议后端在生成数据后使用 schema 进行验证
3. **错误处理**：当数据不符合 schema 时，应该有降级方案（如返回原始数据或错误信息）

### 🔧 可选优化

如果遇到 `$ref` 解析问题，可以考虑：

1. 在生成脚本中添加选项，生成展开版本的 schema（不推荐，文件会变大）
2. 前端提供工具函数，在发送前解析 `$ref`（可选）
3. 后端使用支持 `$ref` 的标准库（推荐）

## 验证测试

建议后端进行以下测试：

1. **Schema 解析测试**：确保可以正确解析带 `$ref` 的 schema
2. **数据生成测试**：使用 schema 指导 LLM 生成数据
3. **数据验证测试**：验证生成的数据是否符合 schema
4. **边界情况测试**：测试缺少必填字段、类型错误等情况

