import * as fs from "fs";
import { createRequire } from "module";
import * as path from "path";
import { dirname } from "path";
import { fileURLToPath } from "url";

// ESM 兼容的 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);

// 使用 require 导入 CommonJS 模块
const TJS: typeof import("typescript-json-schema") = require("typescript-json-schema");

interface SchemaConfig {
  typeName: string;
  sourceFile: string;
  outputPath: string;
}

/**
 * 批量生成 JSON Schema
 * 配置所有需要生成 schema 的组件
 */
const schemaConfigs: SchemaConfig[] = [
  {
    typeName: "WeatherNowProps",
    sourceFile: path.resolve(__dirname, "../src/interfaces/weather.ts"),
    outputPath: path.resolve(
      __dirname,
      "../src/componentTools/components/Weather/WeatherNow/schema.json"
    ),
  },
  // 添加更多组件的配置
  // {
  //   typeName: "AnotherComponentProps",
  //   sourceFile: path.resolve(__dirname, "../src/interfaces/another.ts"),
  //   outputPath: path.resolve(
  //     __dirname,
  //     "../src/componentTools/components/Another/schema.json"
  //   ),
  // },
];

async function generateSchema(config: SchemaConfig) {
  const { typeName, sourceFile, outputPath } = config;

  // 配置 TS Compiler Options
  const compilerOptions = {
    strictNullChecks: true,
    esModuleInterop: true,
    allowSyntheticDefaultImports: true,
    skipLibCheck: true,
    baseUrl: path.resolve(__dirname, ".."),
    paths: {
      "@/*": ["src/*"],
    },
  };

  // 创建 TypeScript 程序
  const program = TJS.getProgramFromFiles([sourceFile], compilerOptions);

  // 创建 Schema 生成器
  const generator = TJS.buildGenerator(program, {
    required: true, // 强制输出必填字段
    strictNullChecks: true,
    ignoreErrors: false, // 显示错误以便调试
  } as any);

  if (!generator) {
    throw new Error(`Schema 生成器创建失败: ${typeName}`);
  }

  // 生成 Schema
  const schema = generator.getSchemaForSymbol(typeName);

  if (!schema) {
    throw new Error(`无法找到类型 "${typeName}"`);
  }

  // 写入文件
  const schemaDir = path.dirname(outputPath);
  if (!fs.existsSync(schemaDir)) {
    fs.mkdirSync(schemaDir, { recursive: true });
  }

  fs.writeFileSync(outputPath, JSON.stringify(schema, null, 2), "utf-8");
  console.log(`✅ ${typeName} Schema 生成成功: ${outputPath}`);
}

async function generateAllSchemas() {
  console.log(`开始生成 ${schemaConfigs.length} 个组件的 Schema...\n`);

  let successCount = 0;
  let failCount = 0;

  for (const config of schemaConfigs) {
    try {
      await generateSchema(config);
      successCount++;
    } catch (error) {
      failCount++;
      console.error(`❌ ${config.typeName} Schema 生成失败:`, error);
      if (error instanceof Error) {
        console.error(error.message);
        console.error(error.stack);
      }
    }
  }

  console.log(`\n✅ 生成完成！成功: ${successCount}, 失败: ${failCount}`);

  if (failCount > 0) {
    process.exit(1);
  }
}

// 运行生成函数
generateAllSchemas().catch(error => {
  console.error("❌ 执行失败:", error);
  process.exit(1);
});

