import type { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import type React from "react";

export type ToolRenderContext = {
  serverName?: string;
  mcpToolName: string;
  toolUseBlock: ToolUseBlock;
  toolResultBlock?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

export type ToolRenderer = {
  icon?: React.ReactNode;
  renderArguments?: (ctx: ToolRenderContext) => React.ReactNode | null;
  renderResult?: (ctx: ToolRenderContext) => React.ReactNode | null;
  getResultLanguage?: (ctx: ToolRenderContext) => string;
};

export type ToolRendererRegistry = Record<string, Record<string, ToolRenderer>>;
