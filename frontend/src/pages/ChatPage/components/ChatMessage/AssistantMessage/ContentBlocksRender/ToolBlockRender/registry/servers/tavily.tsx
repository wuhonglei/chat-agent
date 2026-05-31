import { isWebSearchDisplayItem } from "@/interfaces/contentBlock";
import WebSearchResult from "../../ToolResult/WebSearchResult";
import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import type { ToolRendererRegistry } from "../types";

export const tavilyRenderers: ToolRendererRegistry[string] = {
  web_search: {
    renderResult: ctx => {
      const items = ctx.toolResultBlock?.structuredContentForDisplay?.filter(isWebSearchDisplayItem);
      if (!items?.length) {
        return null;
      }
      return <WebSearchResult items={items} />;
    },
  },
  web_pages_extract: {
    renderResult: renderMarkdownToolResult,
  },
  web_site_crawl: {
    renderResult: renderMarkdownToolResult,
  },
  web_site_map: {
    renderResult: renderMarkdownToolResult,
  },
  research: {
    renderResult: renderMarkdownToolResult,
  },
};
