/** Resolve MCP bare tool name for UI (icons, labels). */

export function displayMcpToolName(block: {
  mcpToolName?: string;
  name?: string;
  serverName?: string;
}): string {
  if (block.mcpToolName) {
    return block.mcpToolName;
  }
  if (block.name && block.serverName && block.name.startsWith(`${block.serverName}_`)) {
    return block.name.slice(block.serverName.length + 1);
  }
  return block.name || "";
}
