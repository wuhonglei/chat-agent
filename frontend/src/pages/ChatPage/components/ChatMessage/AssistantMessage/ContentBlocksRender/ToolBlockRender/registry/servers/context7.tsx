import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import type { ToolRendererRegistry } from "../types";

export const context7Renderers: ToolRendererRegistry[string] = {
  "resolve-library-id": {
    renderResult: renderMarkdownToolResult,
  },
  "query-docs": {
    renderResult: renderMarkdownToolResult,
  },
};
