import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import { Context7Icon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

export const context7Renderers: ToolRendererRegistry[string] = {
  "resolve-library-id": {
    icon: renderIcon(Context7Icon),
    renderResult: renderMarkdownToolResult,
  },
  "query-docs": {
    icon: renderIcon(Context7Icon),
    renderResult: renderMarkdownToolResult,
  },
};
