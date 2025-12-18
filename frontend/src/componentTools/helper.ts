import { ComponentToolItem } from "@/interfaces";
import componentTools from ".";
import { schemaValidator } from "./validate";

type ComponentType =
  | React.ComponentType<Record<string, unknown>>
  | React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>;

export const componentMap = new Map<string, ComponentType>(
  componentTools.map((tool: ComponentToolItem) => [
    tool.name,
    tool.component as ComponentType,
  ])
);

/**
 * 校验 LLM 返回的组件 props 是否合法
 * @param componentName 组件名称
 * @param props 要校验的 props 对象
 * @returns 校验结果对象，包含是否合法和错误信息
 */
export function validateComponentProps(
  componentName: string,
  props: unknown
): {
  valid: boolean;
  errors?: string[];
} {
  return schemaValidator.validateComponentProps(componentName, props);
}
