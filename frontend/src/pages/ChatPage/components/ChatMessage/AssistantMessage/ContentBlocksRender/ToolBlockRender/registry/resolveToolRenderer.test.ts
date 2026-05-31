import { describe, expect, it } from "vitest";

import { formatServerName } from "../ToolBlockTitle/formatServerName";
import { formatToolName } from "../ToolBlockTitle/utils";
import { lookupToolRenderer } from "./lookupToolRenderer";
import { mergeToolRenderer } from "./mergeToolRenderer";
import type { ToolRenderer } from "./types";

const FALLBACK: ToolRenderer = {
  icon: "fallback-icon",
  renderResult: () => "fallback-result",
};

const MOCK_SERVERS: Record<string, Record<string, ToolRenderer>> = {
  tavily: {
    web_search: {
      icon: "tavily-search-icon",
      renderResult: () => "web-search-result",
    },
    web_pages_extract: {
      icon: "tavily-extract-icon",
      renderResult: () => "markdown-result",
    },
  },
};

describe("lookupToolRenderer", () => {
  it("returns tavily web_search renderer with renderResult", () => {
    const renderer = lookupToolRenderer("tavily", "web_search", MOCK_SERVERS, FALLBACK);
    expect(renderer.renderResult?.({} as never)).toBe("web-search-result");
    expect(renderer.icon).toBe("tavily-search-icon");
  });

  it("falls back to default for unknown tool within known server", () => {
    const renderer = lookupToolRenderer("tavily", "unknown_tool", MOCK_SERVERS, FALLBACK);
    expect(renderer.icon).toBe("fallback-icon");
    expect(renderer.renderResult?.({} as never)).toBe("fallback-result");
    expect(renderer.renderArguments).toBeUndefined();
  });

  it("falls back to default for unknown server", () => {
    const renderer = lookupToolRenderer("unknown_server", "web_search", MOCK_SERVERS, FALLBACK);
    expect(renderer).toBe(FALLBACK);
  });

  it("falls back to default when serverName is missing", () => {
    const renderer = lookupToolRenderer(undefined, "web_search", MOCK_SERVERS, FALLBACK);
    expect(renderer).toBe(FALLBACK);
  });
});

describe("mergeToolRenderer", () => {
  it("uses custom handlers when provided", () => {
    const custom: ToolRenderer = {
      icon: "custom-icon",
      renderArguments: () => "args",
    };

    const merged = mergeToolRenderer(custom, FALLBACK);
    expect(merged.icon).toBe("custom-icon");
    expect(merged.renderArguments?.({} as never)).toBe("args");
    expect(merged.renderResult?.({} as never)).toBe("fallback-result");
  });
});

describe("formatServerName", () => {
  it("formats snake_case server keys", () => {
    expect(formatServerName("skill_manager")).toBe("Skill Manager");
    expect(formatServerName("code")).toBe("Code");
    expect(formatServerName("tavily")).toBe("Tavily");
  });
});

describe("tool block title format", () => {
  it("builds source-first title when serverName exists", () => {
    const serverName = "tavily";
    const mcpToolName = "web_search";
    const statusLabel = "工具调用成功";

    const title = `${formatServerName(serverName)} · ${formatToolName(mcpToolName)} · ${statusLabel}`;
    expect(title).toBe("Tavily · Web Search · 工具调用成功");
  });

  it("builds tool-only title when serverName is missing", () => {
    const mcpToolName = "web_search";
    const statusLabel = "工具调用中";

    const title = `${formatToolName(mcpToolName)} · ${statusLabel}`;
    expect(title).toBe("Web Search · 工具调用中");
  });
});
