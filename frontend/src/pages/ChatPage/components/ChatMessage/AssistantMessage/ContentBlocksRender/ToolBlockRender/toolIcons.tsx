import CodeExecIcon from "@/assets/svg/mcp-tools/code-exec.svg?react";
import Context7Icon from "@/assets/svg/mcp-tools/context7.svg?react";
import WeatherIcon from "@/assets/svg/mcp-tools/weather.svg?react";
import WebSearchIcon from "@/assets/svg/mcp-tools/web-search.svg?react";
import { ToolOutlined } from "@ant-design/icons";
import React from "react";

const ICON_CLASS_NAME = "w-4 h-4";

const WEATHER_TOOL_NAMES = new Set([
  "search_city",
  "get_current_weather",
  "get_weather_hourly_forecast",
  "get_weather_daily_forecast",
  "get_weather_alerts",
]);

const WEB_SEARCH_TOOL_NAMES = new Set(["web_search", "web_pages_extract", "web_site_crawl", "web_site_map"]);

const CODE_EXEC_TOOL_NAMES = new Set(["execute_code", "list_runtimes"]);

const CONTEXT7_TOOL_NAMES = new Set([
  "resolve-library-id",
  "get-library-docs",
  "resolve_library_id",
  "get_library_docs",
]);

function normalizeToolName(toolName?: string): string {
  return (toolName || "").trim().toLowerCase();
}

export function getToolIcon(toolName?: string): React.ReactNode {
  const normalizedToolName = normalizeToolName(toolName);

  if (WEATHER_TOOL_NAMES.has(normalizedToolName)) {
    return <WeatherIcon className={ICON_CLASS_NAME} />;
  }

  if (WEB_SEARCH_TOOL_NAMES.has(normalizedToolName)) {
    return <WebSearchIcon className={ICON_CLASS_NAME} />;
  }

  if (CODE_EXEC_TOOL_NAMES.has(normalizedToolName)) {
    return <CodeExecIcon className={ICON_CLASS_NAME} />;
  }

  if (CONTEXT7_TOOL_NAMES.has(normalizedToolName) || normalizedToolName.includes("context7")) {
    return <Context7Icon className={ICON_CLASS_NAME} />;
  }

  return <ToolOutlined />;
}
