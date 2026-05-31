/**
 * Tool renderer registry
 *
 * 新增工具：
 * 1. 在 servers/<server>.ts 注册 { mcpToolName: { icon, renderArguments?, renderResult? } }
 * 2. 仅 result 特化时只实现 renderResult，args 自动 fallback 到默认
 * 3. server 名须与后端 mcp_servers config key 一致（如 tavily、code、shell）
 */
export { DEFAULT_TOOL_RENDERER_ENTRY, SERVER_TOOL_RENDERERS, TOOL_RENDERER_REGISTRY } from "./registryData";
export { mergeToolRenderer } from "./mergeToolRenderer";
export { DEFAULT_TOOL_RENDERER, renderDefaultToolResult } from "./defaults";
export { lookupToolRenderer } from "./lookupToolRenderer";
export { resolveToolContext, resolveToolRenderer, renderToolResult } from "./resolveToolRenderer.ts";
export type { ToolRenderContext, ToolRenderer, ToolRendererRegistry } from "./types";
