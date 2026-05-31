import { lookupToolIcon } from "./icons";
import type { ToolRenderer } from "./types";
import { mergeToolRenderer } from "./mergeToolRenderer";

/** Pure lookup for tests and resolveToolRenderer. */
export function lookupToolRenderer(
  serverName: string | undefined,
  mcpToolName: string,
  servers: Record<string, Record<string, ToolRenderer>>,
  fallback: ToolRenderer
): ToolRenderer {
  const merged = serverName
    ? mergeToolRenderer(servers[serverName]?.[mcpToolName], fallback)
    : fallback;
  return {
    ...merged,
    icon: lookupToolIcon(serverName, mcpToolName, fallback.icon),
  };
}
