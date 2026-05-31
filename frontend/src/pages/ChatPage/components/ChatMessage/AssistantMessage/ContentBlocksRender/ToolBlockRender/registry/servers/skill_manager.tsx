import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import type { ToolRendererRegistry } from "../types";

export const skillManagerRenderers: ToolRendererRegistry[string] = {
  load_skill: {
    renderResult: renderMarkdownToolResult,
  },
};
