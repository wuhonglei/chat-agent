import { isPlainObject } from "lodash-es";

import type { ToolRenderContext } from "../types";

export function parseToolArguments(ctx: ToolRenderContext): Record<string, unknown> | null {
  const { argumentsJson, argumentsText } = ctx.toolUseBlock;
  if (argumentsJson !== undefined && isPlainObject(argumentsJson)) {
    return argumentsJson;
  }
  if (!argumentsText) {
    return null;
  }
  try {
    return JSON.parse(argumentsText) as Record<string, unknown>;
  } catch {
    return null;
  }
}
