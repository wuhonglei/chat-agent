import { isWebSearchDisplayItem } from "@/interfaces/contentBlock";
import WebSearchResult from "../../ToolResult/WebSearchResult";
import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import {
  renderIcon,
  WebCrawlIcon,
  WebExtractIcon,
  WebResearchIcon,
  WebSearchIcon,
} from "../icons";
import type { ToolRendererRegistry } from "../types";

export const tavilyRenderers: ToolRendererRegistry[string] = {
  web_search: {
    icon: renderIcon(WebSearchIcon),
    renderResult: ctx => {
      const items = ctx.toolResultBlock?.structuredContentForDisplay?.filter(isWebSearchDisplayItem);
      if (!items?.length) {
        return null;
      }
      return <WebSearchResult items={items} />;
    },
  },
  web_pages_extract: {
    icon: renderIcon(WebExtractIcon),
    renderResult: renderMarkdownToolResult,
  },
  web_site_crawl: {
    icon: renderIcon(WebCrawlIcon),
    renderResult: renderMarkdownToolResult,
  },
  web_site_map: {
    icon: renderIcon(WebResearchIcon),
    renderResult: renderMarkdownToolResult,
  },
  research: {
    icon: renderIcon(WebResearchIcon),
    renderResult: renderMarkdownToolResult,
  },
};
