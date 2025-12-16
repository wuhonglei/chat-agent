# JSON Schema 自动生成指南

本文档介绍如何根据 TypeScript 组件的 props 类型定义自动生成 JSON Schema。

## 使用方法

### 1. 准备工作

确保你的组件 Props 类型定义在 `src/interfaces/` 目录下，例如：

```typescript
// src/interfaces/weather.ts
export interface WeatherNowProps {
  /** 位置信息 */
  location: string;
  /** 天气数据 */
  data: WeatherNowData;
  /** 空气质量指数（可选） */
  aqi?: {
    level: string;
    category: string;
    aqi?: string;
  };
}
```

### 2. 配置生成脚本

编辑 `scripts/generate-all-schemas.ts` 文件，在 `schemaConfigs` 数组中添加你的组件配置：

```typescript
const schemaConfigs: SchemaConfig[] = [
  {
    typeName: "WeatherNowProps", // 要生成的类型名称
    sourceFile: path.resolve(__dirname, "../src/interfaces/weather.ts"), // 类型定义文件路径
    outputPath: path.resolve(
      __dirname,
      "../src/componentTools/components/Weather/WeatherNow/schema.json"
    ), // 输出文件路径
  },
  // 添加更多组件的配置...
];
```

### 3. 运行生成命令

```bash
npm run generate-all-schemas
```

### 4. 使用生成的 Schema

生成的 schema 会自动保存到指定路径，然后你可以在 `src/componentTools/index.ts` 中导入使用：

```typescript
import weatherNowSchema from "./components/Weather/WeatherNow/schema.json";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather_now",
    component: WeatherNow,
    schema: weatherNowSchema,
    // ...
  },
];
```

## 类型支持

脚本支持以下 TypeScript 类型特性：

- ✅ 基本类型：`string`, `number`, `boolean`
- ✅ 对象类型：`object`, 嵌套对象
- ✅ 数组类型：`Array<T>`, `T[]`
- ✅ 可选属性：`prop?: type`
- ✅ 必填属性（自动识别）
- ✅ 注释：JSDoc 注释会转换为 `description`
- ✅ 类型引用：使用 `$ref` 引用其他类型定义

## 注意事项

1. **路径别名**：脚本支持 `@/*` 路径别名，确保类型定义文件中的导入路径正确。

2. **类型导出**：确保要生成的类型是 `export` 导出的，且类型名称与配置中的 `typeName` 完全一致。

3. **必需字段识别**：脚本会自动识别哪些字段是必需的（没有 `?` 的字段）。

4. **嵌套类型**：如果类型引用了其他类型（如 `WeatherNowData`），它们会被自动提取到 `definitions` 中。

5. **可选字段**：可选字段（使用 `?` 标记）不会出现在 `required` 数组中。

## 示例

完整的生成流程示例：

```bash
# 1. 编辑脚本配置
vim scripts/generate-all-schemas.ts

# 2. 运行生成命令
npm run generate-all-schemas

# 输出：
# ✅ Schema 生成成功！
# 📄 类型: WeatherNowProps
# 📝 源文件: /path/to/src/interfaces/weather.ts
# 💾 输出文件: /path/to/schema.json
```

## 故障排查

### 问题：找不到类型

**错误信息**：`❌ 无法找到类型 "YourTypeName"`

**解决方案**：
1. 检查类型名称是否正确（大小写敏感）
2. 确保类型是 `export` 导出的
3. 检查源文件路径是否正确

### 问题：路径解析错误

**错误信息**：模块找不到等

**解决方案**：
1. 确保 `tsconfig.json` 中配置了路径别名
2. 检查 `baseUrl` 和 `paths` 配置是否正确

### 问题：生成的 schema 缺少某些字段

**可能原因**：
- 字段使用了不支持的类型（如函数类型）
- 字段使用了泛型且未指定具体类型

**解决方案**：检查类型定义，确保所有字段都是 JSON Schema 支持的类型。

