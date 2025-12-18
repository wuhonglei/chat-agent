import type { ValidateFunction } from "ajv";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import type { JSONSchema7 } from "json-schema";

/**
 * 组件 Schema 验证器类
 * 负责加载和验证组件的 JSON Schema
 */
class ComponentSchemaValidator {
  private ajv: Ajv;
  private schemaMap: Map<string, JSONSchema7>;
  private schemaCache: Map<string, ValidateFunction>;

  constructor() {
    // 创建 AJV 实例，支持 JSON Schema Draft 7 和格式验证
    this.ajv = new Ajv({
      allErrors: true, // 收集所有错误
      strict: false, // 允许非严格模式，兼容更多 schema
      validateFormats: true, // 验证格式
    });
    addFormats(this.ajv);

    // 使用 Vite 的 import.meta.glob 动态导入所有 schema 文件
    const schemaModules = import.meta.glob<JSONSchema7>(
      "./component-schemas/*.json",
      { eager: true, import: "default" }
    );

    // 创建组件名称到 schema 的映射
    // 从 glob 返回的 key 中提取组件名称（文件名）
    this.schemaMap = new Map<string, JSONSchema7>();
    for (const [path, schema] of Object.entries(schemaModules)) {
      // 从路径中提取文件名（组件名称）
      // 例如：../component-schemas/weather.json -> weather
      const match = path.match(/([^/]+)\.json$/);
      if (match && match[1]) {
        this.schemaMap.set(match[1], schema);
      }
    }

    // Schema 缓存：组件名称 -> 验证函数
    this.schemaCache = new Map<string, ValidateFunction>();
  }

  /**
   * 加载组件的 JSON Schema
   * @param componentName 组件名称
   * @returns ValidateFunction | null 返回验证函数，如果加载失败返回 null
   */
  private loadComponentSchema(componentName: string): ValidateFunction | null {
    // 检查缓存
    if (this.schemaCache.has(componentName)) {
      return this.schemaCache.get(componentName)!;
    }

    try {
      // 从预加载的 schema 映射中获取
      const schema = this.schemaMap.get(componentName);

      if (!schema) {
        console.warn(`无法找到组件 ${componentName} 的 schema`);
        return null;
      }

      // 编译 schema
      const validate = this.ajv.compile(schema);

      // 缓存验证函数
      this.schemaCache.set(componentName, validate);

      return validate;
    } catch (error) {
      console.error(`加载组件 ${componentName} 的 schema 失败:`, error);
      return null;
    }
  }

  /**
   * 校验 LLM 返回的组件 props 是否合法
   * @param componentName 组件名称
   * @param props 要校验的 props 对象
   * @returns 校验结果对象，包含是否合法和错误信息
   */
  validateComponentProps(
    componentName: string,
    props: unknown
  ): {
    valid: boolean;
    errors?: string[];
  } {
    // 加载 schema
    const validate = this.loadComponentSchema(componentName);

    if (!validate) {
      // 如果无法加载 schema，返回警告但不阻止使用
      console.warn(`组件 ${componentName} 的 schema 未找到，跳过校验`);
      return {
        valid: true, // 允许通过，但记录警告
      };
    }

    // 执行校验
    const valid = validate(props);

    if (valid) {
      return { valid: true };
    }

    // 收集错误信息
    const errors = validate.errors?.map(error => {
      const path = error.instancePath || "root";
      const message = error.message || "未知错误";
      return `${path}: ${message}`;
    }) || ["校验失败"];

    return {
      valid: false,
      errors,
    };
  }
}

// 创建单例实例
export const schemaValidator = new ComponentSchemaValidator();
