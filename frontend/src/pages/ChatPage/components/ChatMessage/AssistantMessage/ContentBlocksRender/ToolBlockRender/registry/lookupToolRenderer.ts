import type { ToolRenderer } from "./types";
import { mergeToolRenderer } from "./mergeToolRenderer";

/** Pure lookup for tests and resolveToolRenderer. */
export function lookupToolRenderer(
  serverName: string | undefined,
  mcpToolName: string,
  servers: Record<string, Record<string, ToolRenderer>>,
  fallback: ToolRenderer
): ToolRenderer {
  if (!serverName) {
    return fallback;
  }
  return mergeToolRenderer(servers[serverName]?.[mcpToolName], fallback);
}
