# 组件工具实现方案

## 需求概述

1. **AI回复中特定的code块使用组件进行渲染**
2. **组件的JSON schema定义在构建时生成，存放到 public 目录**
3. **前端请求后端时，只传递组件名称，不传递具体的 JSON schema**
4. **后端收到请求后，根据组件名称请求获取具体的 JSON schema**
5. **后端根据聊天内容选择性生成组件的prop data**

## 架构设计

### 数据流

```
前端注册组件（使用 props 类型） → Vite 构建时生成 JSON schema 到 public 目录 →
前端发送请求时只传递组件名称 → 后端根据组件名称请求获取 schema →
后端根据条件生成组件数据 → 后端返回带组件标识的 code 块 → 前端解析并渲染组件
```

### 组件注册机制

在 `src/componentTools/index.ts` 中注册所有组件工具，每个组件包含：
- `name`: 组件唯一标识
- `component`: React 组件
- `props`: TypeScript 类型定义（组件的 Props 类型）
- `when`: 触发条件（tool_names, tool_call_content, user_message_content, assistant_message_content）

### Schema 生成机制

- **构建时生成**：使用 Vite 插件在构建时根据组件的 Props 类型自动生成 JSON Schema
- **存储位置**：生成的 JSON Schema 文件存放到 `public/component-schemas/` 目录
- **文件命名**：`{component_name}.json`（例如：`weather_now.json`）
- **访问方式**：后端可通过 `/component-schemas/{component_name}.json` 获取 schema

## 实现步骤

### 步骤1: 修改 ComponentToolItem 接口

在 `src/interfaces/componentTools.ts` 中修改接口定义：

```typescript
/**
 * 组件工具的请求项（发送给后端）
 * 只包含组件名称和触发条件，不包含 schema
 */
export interface ComponentToolRequestItem {
  name: string;
  when: {
    tool_names?: string[]; // 当 mcp 工具名称匹配时，后端才会组装对应的组件
    tool_call_content?: string[]; // 当 mcp 工具调用内容匹配时，后端才会组装对应的组件
    user_message_content?: string[]; // 当用户消息内容匹配时，后端才会组装对应的组件
    assistant_message_content?: string[]; // 当 ai 消息内容匹配时，后端才会组装对应的组件
  };
}

/**
 * 组件工具项（前端注册使用）
 */
export interface ComponentToolItem<T = any> {
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: React.ComponentType<any>;
  props: T; // TypeScript 类型定义（用于生成 JSON Schema）
  when: ComponentToolRequestItem["when"];
}
```

### 步骤2: 扩展 ChatRequest 接口

在 `src/interfaces/chat.ts` 中添加 `componentTools` 字段：

```typescript
import { ComponentToolRequestItem } from "./componentTools";

export interface ChatRequest extends ChatInputFormValues {
  conversationId?: string;
  historyIds: string[];
  regenerateTitle: boolean;
  removedMessageIds: string[];
  componentTools?: ComponentToolRequestItem[]; // 新增：组件工具定义（只包含 name 和 when）
}
```

### 步骤3: 创建工具函数获取组件工具请求数据

在 `src/utils/componentTools.ts` 中创建工具函数：

```typescript
import componentTools from "@/componentTools";
import { ComponentToolRequestItem } from "@/interfaces/componentTools";

/**
 * 获取组件工具的请求数据（只包含后端需要的字段：name 和 when）
 * 用于在发送聊天请求时传递给后端
 * 注意：不包含 schema，后端需要根据 name 自行获取 schema
 */
export function getComponentToolsRequestData(): ComponentToolRequestItem[] {
  return componentTools.map(({ name, when }) => ({
    name,
    when,
  }));
}
```

### 步骤4: 在发送消息时携带组件工具定义

修改 `src/hooks/chat.ts` 中的 `sendMessage` 函数，在调用 `chatAPI.streamMessage` 时添加 `componentTools`：

```typescript
import { getComponentToolsRequestData } from "@/utils/componentTools";

// 在 sendMessage 函数中
await chatAPI.streamMessage(
  {
    ...values,
    historyIds,
    regenerateTitle,
    removedMessageIds,
    conversationId,
    componentTools: getComponentToolsRequestData(), // 新增：只传递 name 和 when
  },
  // ... 其他参数
);
```

### 步骤5: 通用化 MarkdownContainer 中的组件渲染逻辑

修改 `src/pages/ChatPage/components/MarkdownContainer/index.tsx`，使其能够根据组件名称动态渲染组件：

```typescript
import componentTools from "@/componentTools";
import { ComponentToolItem } from "@/interfaces/componentTools";

// 创建组件名称到组件的映射
const componentMap = new Map<string, ComponentToolItem["component"]>();
componentTools.forEach(tool => {
  componentMap.set(tool.name, tool.component);
});

// 在 CustomCodeBlock 中
const CustomCodeBlock = memo(({ inline, className, children }: CustomCodeBlockProps) => {
  const code = String(children).replace(/\n$/, "");
  const language = useLanguage(className, code, inline);

  // 检查是否是组件代码块（格式：component_<component_name>）
  if (!inline && language?.startsWith("component_")) {
    const componentName = language.replace("component_", "");
    const Component = componentMap.get(componentName);

    if (Component) {
      try {
        const parsedData = JSON.parse(jsonrepair(code));
        return (
          <ComponentErrorBoundary
            fallbackCode={code}
            fallbackLang="json"
            onError={handleError}
          >
            <Component {...parsedData} />
          </ComponentErrorBoundary>
        );
      } catch (error) {
        console.warn(`组件 ${componentName} JSON 解析失败，降级为代码展示:`, error);
        return <CodeHighlighter lang="json">{code}</CodeHighlighter>;
      }
    }
  }

  // ... 其他逻辑（mermaid, 普通代码块等）
});
```

### 步骤6: 创建 Vite 插件生成 JSON Schema

#### 6.1 创建 Vite 插件

创建 `vite-plugins/generate-component-schemas.ts`：

```typescript
import * as fs from "fs";
import * as path from "path";
import type { Plugin } from "vite";
import { createRequire } from "module";

const require = createRequire(import.meta.url);

const TJS: typeof import("typescript-json-schema") = require("typescript-json-schema");

interface ComponentSchemaConfig {
  name: string;
  typeName: string;
  sourceFile: string;
}

/**
 * 从 componentTools/index.ts 中提取组件配置
 * 这里需要解析文件或使用配置数组
 */
const componentConfigs: ComponentSchemaConfig[] = [
  {
    name: "weather_now",
    typeName: "WeatherNowProps",
    sourceFile: path.resolve(process.cwd(), "src/componentTools/components/WeatherNow/type.ts"),
  },
  // 添加更多组件的配置
];

/**
 * Vite 插件：在构建时生成组件的 JSON Schema
 */
export function generateComponentSchemas(): Plugin {
  return {
    name: "generate-component-schemas",
    buildStart() {
      const outputDir = path.resolve(process.cwd(), "public/component-schemas");

      // 确保输出目录存在
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
      }

      console.log(`开始生成 ${componentConfigs.length} 个组件的 Schema...\n`);

      for (const config of componentConfigs) {
        try {
          const compilerOptions = {
            strictNullChecks: true,
            esModuleInterop: true,
            allowSyntheticDefaultImports: true,
            skipLibCheck: true,
            baseUrl: process.cwd(),
            paths: {
              "@/*": ["src/*"],
            },
          };

          const program = TJS.getProgramFromFiles([config.sourceFile], compilerOptions);
          const generator = TJS.buildGenerator(program, {
            required: true,
            strictNullChecks: true,
            ignoreErrors: false,
          } as any);

          if (!generator) {
            throw new Error(`Schema 生成器创建失败: ${config.typeName}`);
          }

          const schema = generator.getSchemaForSymbol(config.typeName);

          if (!schema) {
            throw new Error(`无法找到类型 "${config.typeName}"`);
          }

          const outputPath = path.join(outputDir, `${config.name}.json`);
          fs.writeFileSync(outputPath, JSON.stringify(schema, null, 2), "utf-8");
          console.log(`✅ ${config.name} Schema 生成成功: ${outputPath}`);
        } catch (error) {
          console.error(`❌ ${config.name} Schema 生成失败:`, error);
          if (error instanceof Error) {
            console.error(error.message);
          }
        }
      }

      console.log(`\n✅ 所有 Schema 生成完成！`);
    },
  };
}
```

#### 6.2 在 vite.config.ts 中使用插件

修改 `vite.config.ts`：

```typescript
import { generateComponentSchemas } from "./vite-plugins/generate-component-schemas";

export default defineConfig(({ mode }) => {
  // ... 其他配置

  return {
    plugins: [
      react(),
      tailwindcss(),
      svgr({
        svgrOptions: {
          icon: true,
        },
      }),
      generateComponentSchemas(), // 新增：在构建时生成 schema
    ],
    // ... 其他配置
  };
});
```

#### 6.3 Schema 文件位置

生成的 JSON Schema 文件将存放在：
- `public/component-schemas/weather_now.json`
- `public/component-schemas/{component_name}.json`

构建后，这些文件可以通过以下 URL 访问：
- `/component-schemas/weather_now.json`
- `/component-schemas/{component_name}.json`

### 步骤7: 在 componentTools/index.ts 中使用 props 定义

修改 `src/componentTools/index.ts`，使用 props 类型定义而不是 schema：

```typescript
import { ComponentToolItem } from "@/interfaces";
import WeatherNow from "./components/WeatherNow";
import type { WeatherNowProps } from "./components/WeatherNow/type";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather_now",
    component: WeatherNow,
    props: {} as WeatherNowProps, // 使用类型定义，用于 Vite 插件生成 schema
    when: {
      tool_names: ["weather"],
    },
  },
];

export default componentTools;
```

**注意**：`props: {} as WeatherNowProps` 只是用于类型推断，实际值不会被使用。Vite 插件会从类型定义中提取信息生成 JSON Schema。

## 后端交互协议

### 请求格式

前端发送请求时，`componentTools` 字段格式（**只包含组件名称和触发条件，不包含 schema**）：

```json
{
  "content": "用户消息",
  "component_tools": [
    {
      "name": "weather_now",
      "when": {
        "tool_names": ["weather"]
      }
    }
  ]
}
```

### 后端获取 Schema

后端收到请求后，需要根据组件名称获取对应的 JSON Schema：

**获取方式**：通过 HTTP 请求获取
- URL 格式：`{前端域名}/component-schemas/{component_name}.json`
- 示例：`https://example.com/component-schemas/weather_now.json`

**示例请求**：
```http
GET /component-schemas/weather_now.json HTTP/1.1
Host: example.com
```

**响应示例**：
```json
{
  "type": "object",
  "properties": {
    "location": { "type": "string" },
    "data": {
      "type": "object",
      "properties": {
        "obsTime": { "type": "string" },
        "temp": { "type": "string" },
        ...
      },
      "required": ["obsTime", "temp", ...]
    }
  },
  "required": ["location", "data"]
}
```

### 后端返回格式

后端在 AI 回复中，当满足条件时，应该返回如下格式的代码块：

````markdown
```component_weather_now
{
  "location": "北京",
  "data": {
    "obsTime": "2024-01-01T12:00+08:00",
    "temp": "15",
    ...
  }
}
```
````

代码块的语言标识格式：`component_<component_name>`

## 添加新组件的流程

1. **创建组件**：在 `src/componentTools/components/` 下创建新组件
2. **定义类型**：在组件目录下定义组件的 Props 类型（例如：`type.ts`）
3. **注册组件**：在 `src/componentTools/index.ts` 中添加组件注册，使用 `props` 字段指定类型
4. **配置 Vite 插件**：在 `vite-plugins/generate-component-schemas.ts` 的 `componentConfigs` 数组中添加组件配置
5. **配置触发条件**：设置 `when` 字段，定义何时后端应该生成该组件
6. **构建生成 Schema**：运行 `npm run build`，Vite 插件会自动生成 JSON Schema 到 `public/component-schemas/` 目录

## 注意事项

1. **Schema 同步**：确保生成的 JSON Schema 与 TypeScript 类型定义保持一致，每次修改类型后需要重新构建
2. **构建时生成**：JSON Schema 在构建时生成，开发环境不会自动生成，需要运行构建命令
3. **Schema 访问**：确保构建后的 `public/component-schemas/` 目录可以被后端访问
4. **错误处理**：组件渲染失败时，应该降级为代码展示
5. **性能优化**：组件映射表在模块加载时创建，避免重复创建
6. **类型安全**：使用 TypeScript 确保类型安全，避免运行时错误
7. **后端缓存**：建议后端缓存获取到的 JSON Schema，避免频繁请求

## 示例：添加新组件

假设要添加一个 `Chart` 组件：

1. **创建组件文件**：
   ```
   src/componentTools/components/Chart/index.tsx
   ```

2. **定义类型**：
   ```typescript
   // src/componentTools/components/Chart/type.ts
   export interface ChartProps {
     type: "line" | "bar" | "pie";
     data: number[];
     labels: string[];
   }
   ```

3. **注册组件**：
   ```typescript
   // src/componentTools/index.ts
   import Chart from "./components/Chart";
   import type { ChartProps } from "./components/Chart/type";

   const componentTools: ComponentToolItem[] = [
     // ... 现有组件
     {
       name: "chart",
       component: Chart,
       props: {} as ChartProps, // 用于类型推断和生成 schema
       when: {
         tool_names: ["data_visualization"],
       },
     },
   ];
   ```

4. **配置 Vite 插件**：
   ```typescript
   // vite-plugins/generate-component-schemas.ts
   const componentConfigs: ComponentSchemaConfig[] = [
     // ... 现有配置
     {
       name: "chart",
       typeName: "ChartProps",
       sourceFile: path.resolve(process.cwd(), "src/componentTools/components/Chart/type.ts"),
     },
   ];
   ```

5. **构建生成 Schema**：
   ```bash
   npm run build
   ```
   构建完成后，会在 `public/component-schemas/chart.json` 生成 JSON Schema。

6. **后端获取 Schema**：
   后端可以通过 `GET /component-schemas/chart.json` 获取该组件的 JSON Schema。

7. **后端返回**：
   ```markdown
   ```component_chart
   {
     "type": "line",
     "data": [1, 2, 3, 4, 5],
     "labels": ["Jan", "Feb", "Mar", "Apr", "May"]
   }
   ```
   ```

