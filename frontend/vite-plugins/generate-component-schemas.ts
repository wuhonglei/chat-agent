import debug from "debug";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { dirname, relative, resolve } from "path";
import * as ts from "typescript";
import * as TJS from "typescript-json-schema";
import { fileURLToPath } from "url";
import type { Plugin } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// 创建日志命名空间
const log = debug("vite-plugin:component-schemas");
const logError = debug("vite-plugin:component-schemas:error");
const logWarn = debug("vite-plugin:component-schemas:warn");

// 启用错误和警告日志（即使 DEBUG 未设置也会显示）
logError.enabled = true;
logWarn.enabled = true;

/**
 * 从 TypeScript 文件中提取导出的接口名称
 * 优先查找以 Props 结尾的接口（组件 Props 类型）
 */
function extractExportedInterfaceName(filePath: string): string | null {
  try {
    const content = readFileSync(filePath, "utf-8");

    // 查找所有导出的接口
    const allInterfaces = Array.from(
      content.matchAll(/export\s+(interface|type)\s+(\w+)/g)
    );

    if (allInterfaces.length === 0) {
      return null;
    }

    // 优先查找以 Props 结尾的接口（组件 Props 类型）
    const propsInterface = allInterfaces.find(m => m[2].endsWith("Props"));
    if (propsInterface) {
      return propsInterface[2];
    }

    // 如果没有找到 Props 接口，返回最后一个（通常是主要的导出接口）
    return allInterfaces.at(-1)[2];
  } catch (error) {
    logError(`读取文件 ${filePath} 失败:`, error);
    return null;
  }
}

/**
 * 读取 TypeScript 配置
 */
function getTypeScriptConfig(projectRoot: string): ts.CompilerOptions {
  const tsconfigPath = resolve(projectRoot, "tsconfig.json");

  if (existsSync(tsconfigPath)) {
    try {
      const configFile = ts.readConfigFile(tsconfigPath, path =>
        readFileSync(path, "utf-8")
      );
      const parsedConfig = ts.parseJsonConfigFileContent(
        configFile.config,
        ts.sys,
        projectRoot
      );

      // 确保 baseUrl 和 paths 正确设置
      // typescript-json-schema 需要 Node 解析模式，而不是 Bundler
      const options: ts.CompilerOptions = {
        ...parsedConfig.options,
        baseUrl: parsedConfig.options.baseUrl || projectRoot,
        paths: parsedConfig.options.paths || {
          "@/*": ["src/*"],
        },
        // 覆盖 moduleResolution 为 NodeJs，以便 typescript-json-schema 能正确解析
        moduleResolution: ts.ModuleResolutionKind.Node10,
      };

      return options;
    } catch (error) {
      logWarn(`读取 tsconfig.json 失败，使用默认配置:`, error);
    }
  }

  // 默认配置
  return {
    strictNullChecks: true,
    esModuleInterop: true,
    skipLibCheck: true,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.NodeJs, // typescript-json-schema 需要 Node 解析模式
    target: ts.ScriptTarget.ES2020,
    baseUrl: projectRoot,
    paths: {
      "@/*": ["src/*"],
    },
  };
}

/**
 * 生成单个组件的 JSON Schema
 */
function generateSchema(
  componentName: string,
  typeSourceFile: string,
  outputDir: string,
  projectRoot: string
): boolean {
  try {
    const absoluteTypeFile = resolve(projectRoot, typeSourceFile);

    if (!existsSync(absoluteTypeFile)) {
      logError(`类型文件不存在: ${absoluteTypeFile}`);
      return false;
    }

    // 提取接口名称
    const interfaceName = extractExportedInterfaceName(absoluteTypeFile);
    if (!interfaceName) {
      logError(`无法从 ${absoluteTypeFile} 中提取接口名称`);
      return false;
    }

    log(`正在为组件 ${componentName} 生成 Schema (接口: ${interfaceName})...`);

    // 获取 TypeScript 配置
    const compilerOptions = getTypeScriptConfig(projectRoot);

    // 创建 TypeScript 编译器程序
    const program = TJS.getProgramFromFiles(
      [absoluteTypeFile],
      compilerOptions,
      projectRoot
    );

    // 生成 JSON Schema
    const schema = TJS.generateSchema(program, interfaceName, {
      required: true,
      noExtraProps: false,
      strictNullChecks: true,
    });

    if (!schema) {
      logError(`无法为 ${interfaceName} 生成 Schema`);
      return false;
    }

    // 确保输出目录存在
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    // 写入文件
    const outputPath = resolve(outputDir, `${componentName}.json`);
    writeFileSync(outputPath, JSON.stringify(schema, null, 2), "utf-8");

    log(`✓ Schema 已生成: ${outputPath}`);
    return true;
  } catch (error) {
    logError(`生成组件 ${componentName} 的 Schema 失败:`, error);
    return false;
  }
}

/**
 * 从 componentTools/index.ts 中提取组件信息
 */
function extractComponentTools(
  projectRoot: string
): Array<{ name: string; typeSourceFile: string }> {
  const indexPath = resolve(projectRoot, "src/componentTools/index.ts");

  if (!existsSync(indexPath)) {
    logError(`组件工具索引文件不存在: ${indexPath}`);
    return [];
  }

  try {
    const content = readFileSync(indexPath, "utf-8");
    const componentToolsDir = dirname(indexPath);

    // 使用正则表达式提取组件信息
    // 匹配: { name: "xxx", component: Xxx, typeSourceFile: require.resolve("..."), ... }
    // 支持多行匹配（使用 [\s\S] 代替 . 来匹配包括换行符在内的所有字符）
    const componentMatches = content.matchAll(
      /\{\s*name:\s*["']([^"']+)["'],[\s\S]*?component:\s*\w+,[\s\S]*?typeSourceFile:\s*require\.resolve\(["']([^"']+)["']\)/g
    );

    const components: Array<{ name: string; typeSourceFile: string }> = [];

    for (const match of Array.from(componentMatches)) {
      const name = match[1];
      const typeSourceFile = match[2];

      // require.resolve() 中的路径是相对于 componentTools/index.ts 的
      // 需要解析为绝对路径
      const absoluteTypeFile = resolve(componentToolsDir, typeSourceFile);

      // 转换为相对于项目根目录的路径
      const relativePath = relative(projectRoot, absoluteTypeFile);
      components.push({ name, typeSourceFile: relativePath });
    }

    return components;
  } catch (error) {
    logError(`解析组件工具索引文件失败:`, error);
    return [];
  }
}

/**
 * Vite 插件：生成组件 JSON Schema
 */
export function generateComponentSchemas(): Plugin {
  return {
    name: "generate-component-schemas",
    buildStart() {
      const projectRoot = resolve(__dirname, "..");
      const outputDir = resolve(projectRoot, "public/component-schemas");

      log("开始生成组件 JSON Schema...");

      // 提取组件信息
      const components = extractComponentTools(projectRoot);

      if (components.length === 0) {
        logWarn("未找到任何组件工具");
        return;
      }

      log(`找到 ${components.length} 个组件工具`);

      // 为每个组件生成 Schema
      let successCount: number = 0;
      for (const component of components) {
        if (
          generateSchema(
            component.name,
            component.typeSourceFile,
            outputDir,
            projectRoot
          )
        ) {
          successCount++;
        }
      }

      log(`Schema 生成完成: ${successCount}/${components.length} 成功`);
    },
  };
}
