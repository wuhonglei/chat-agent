import type { ToolUseBlock } from "@/interfaces/contentBlock";
import { displayMcpToolName } from "@/utils/toolNaming";

import { renderDefaultToolResult } from "./defaults";
import { DEFAULT_TOOL_RENDERER_ENTRY, SERVER_TOOL_RENDERERS } from "./registryData";
import { lookupToolRenderer } from "./lookupToolRenderer";
import type { ToolRenderContext, ToolRenderer } from "./types";

export function resolveToolContext(
  block: ToolUseBlock
): Pick<ToolRenderContext, "serverName" | "mcpToolName"> {
  return {
    serverName: block.serverName,
    mcpToolName: displayMcpToolName(block),
  };
}

export function resolveToolRenderer(serverName: string | undefined, mcpToolName: string): ToolRenderer {
  return lookupToolRenderer(serverName, mcpToolName, SERVER_TOOL_RENDERERS, DEFAULT_TOOL_RENDERER_ENTRY);
}

export function renderToolResult(ctx: ToolRenderContext, renderer: ToolRenderer) {
  const custom = renderer.renderResult?.(ctx);
  if (custom != null) {
    return custom;
  }
  return renderDefaultToolResult(ctx);
}
