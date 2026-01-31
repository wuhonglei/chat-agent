/**
 * 从 TypeScript 类型定义生成 JSON Schema 的工具函数
 *
 * 使用方法：
 * 1. 根据组件的 Props 接口手动定义 JSON Schema
 * 2. 使用辅助函数简化常见类型的 schema 定义
 */

import type { JSONSchema7 } from "json-schema";

/**
 * 从组件的 props 类型生成 JSON Schema
 * 这是一个辅助函数，需要手动定义 schema，但提供类型检查
 *
 * @example
 * const schema = createComponentSchema({
 *   type: "object",
 *   properties: {
 *     name: { type: "string" },
 *     age: { type: "number" }
 *   },
 *   required: ["name"]
 * });
 */
export function createComponentSchema(schema: JSONSchema7): JSONSchema7 {
  return schema;
}

/**
 * 创建字符串类型的 schema
 */
export function stringSchema(description?: string): JSONSchema7 {
  return {
    type: "string",
    ...(description && { description }),
  };
}

/**
 * 创建数字类型的 schema
 */
export function numberSchema(description?: string): JSONSchema7 {
  return {
    type: "number",
    ...(description && { description }),
  };
}

/**
 * 创建布尔类型的 schema
 */
export function booleanSchema(description?: string): JSONSchema7 {
  return {
    type: "boolean",
    ...(description && { description }),
  };
}

/**
 * 创建对象类型的 schema
 */
export function objectSchema(
  properties: Record<string, JSONSchema7>,
  required?: string[],
  description?: string
): JSONSchema7 {
  return {
    type: "object",
    properties,
    ...(required && { required }),
    ...(description && { description }),
  };
}

/**
 * 创建数组类型的 schema
 */
export function arraySchema(items: JSONSchema7, description?: string): JSONSchema7 {
  return {
    type: "array",
    items,
    ...(description && { description }),
  };
}

/**
 * 创建可选字段的 schema（用于可选属性）
 */
export function optionalSchema(schema: JSONSchema7): JSONSchema7 {
  return schema;
}
