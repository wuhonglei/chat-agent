# JSON Schema 自动生成指南

> **注意**：本文档已过时。脚本生成方式已移除，现在使用 Vite 插件在构建时自动生成 Schema。
>
> 请参考 [组件工具实现方案](./component-tools-implementation.md) 了解当前的 Schema 生成方式。

## 当前实现方式

Schema 现在通过 Vite 插件在构建时自动生成。插件会：

1. 读取 `src/componentTools/index.ts` 模块
2. 遍历 `componentTools` 数组，提取每个组件的 `name` 和 `typeSourceFile`
3. 从 `typeSourceFile` 指定的文件中解析类型定义（如 `WeatherNowProps`）
4. 使用 `typescript-json-schema` 生成 JSON Schema
5. 将 Schema 文件输出到 `public/component-schemas/{component_name}.json`

### 组件注册

在 `src/componentTools/index.ts` 中注册组件时，使用 `typeSourceFile` 字段指定类型定义文件路径：

```typescript
import { ComponentToolItem } from "@/interfaces";
import { createRequire } from "module";
import WeatherNow from "./components/WeatherNow";

const require = createRequire(import.meta.url);

const componentTools: ComponentToolItem[] = [
  {
    name: "weather_now",
    component: WeatherNow,
    typeSourceFile: require.resolve("./components/WeatherNow/type.ts"),
    when: {
      tool_names: ["weather"],
    },
  },
];
```

### 生成 Schema

运行构建命令即可自动生成 Schema：

```bash
npm run build
```

生成的 Schema 文件将位于 `public/component-schemas/{component_name}.json`。

## 类型支持

Schema 生成支持以下 TypeScript 类型特性：

- ✅ 基本类型：`string`, `number`, `boolean`
- ✅ 对象类型：`object`, 嵌套对象
- ✅ 数组类型：`Array<T>`, `T[]`
- ✅ 可选属性：`prop?: type`
- ✅ 必填属性（自动识别）
- ✅ 注释：JSDoc 注释会转换为 `description`
- ✅ 类型引用：使用 `$ref` 引用其他类型定义

## 更多信息

详细的实现说明请参考 [组件工具实现方案](./component-tools-implementation.md) 文档。
