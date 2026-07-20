import { isPlainObject } from "lodash-es";
import { Allow, parse as parsePartialJson } from "partial-json";

import type { ToolRenderContext } from "../types";

/** 流式组装中允许不完整 object / string，以便尽早展示 file 等内容。 */
const PARTIAL_JSON_ALLOW = Allow.OBJ | Allow.STR;

function tryParseArgumentsText(argumentsText: string): Record<string, unknown> | null {
  const trimmed = argumentsText.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    return isPlainObject(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    // 流式过程中 JSON 尚未闭合，继续尝试 partial parse
  }

  try {
    const parsed = parsePartialJson(trimmed, PARTIAL_JSON_ALLOW) as unknown;
    return isPlainObject(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function parseToolArguments(ctx: ToolRenderContext): Record<string, unknown> | null {
  const { argumentsJson, argumentsText } = ctx.toolUseBlock;
  if (argumentsJson !== undefined && isPlainObject(argumentsJson)) {
    return argumentsJson;
  }
  if (!argumentsText) {
    return null;
  }
  return tryParseArgumentsText(argumentsText);
}

/** 导出供单测使用 */
export { tryParseArgumentsText as parseToolArgumentsTextForTest };
