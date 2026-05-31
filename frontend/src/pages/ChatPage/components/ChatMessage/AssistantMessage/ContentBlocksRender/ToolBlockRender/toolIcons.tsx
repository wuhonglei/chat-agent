import CodeExecIcon from "@/assets/svg/mcp-tools/code-exec.svg?react";
import Context7Icon from "@/assets/svg/mcp-tools/context7.svg?react";
import EditFileIcon from "@/assets/svg/mcp-tools/edit-file.svg?react";
import LoadSkillIcon from "@/assets/svg/mcp-tools/load-skill.svg?react";
import PresentFilesIcon from "@/assets/svg/mcp-tools/present-files.svg?react";
import ReadFileIcon from "@/assets/svg/mcp-tools/read-file.svg?react";
import SearchFilesIcon from "@/assets/svg/mcp-tools/search-files.svg?react";
import ShellIcon from "@/assets/svg/mcp-tools/shell.svg?react";
import TimeIcon from "@/assets/svg/mcp-tools/time.svg?react";
import WeatherIcon from "@/assets/svg/mcp-tools/weather.svg?react";
import WebCrawlIcon from "@/assets/svg/mcp-tools/web-crawl.svg?react";
import WebExtractIcon from "@/assets/svg/mcp-tools/web-extract.svg?react";
import WebResearchIcon from "@/assets/svg/mcp-tools/web-research.svg?react";
import WebSearchIcon from "@/assets/svg/mcp-tools/web-search.svg?react";
import WriteFileIcon from "@/assets/svg/mcp-tools/write-file.svg?react";
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

const CODE_EXEC_TOOL_NAMES = new Set(["execute_code", "list_runtimes"]);

const FILE_TOOL_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  read_file: ReadFileIcon,
  write_file: WriteFileIcon,
  edit_file: EditFileIcon,
  search_files: SearchFilesIcon,
  present_files: PresentFilesIcon,
};

export const CONTEXT7_TOOL_NAMES = new Set(["resolve-library-id", "query-docs"]);

function normalizeToolName(toolName?: string): string {
  return (toolName || "").trim().toLowerCase();
}

export function getToolIcon(toolName?: string): React.ReactNode {
  const normalizedToolName = normalizeToolName(toolName);

  if (WEATHER_TOOL_NAMES.has(normalizedToolName)) {
    return <WeatherIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "web_search") {
    return <WebSearchIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "web_pages_extract") {
    return <WebExtractIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "web_site_crawl") {
    return <WebCrawlIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "web_site_map" || normalizedToolName === "research") {
    return <WebResearchIcon className={ICON_CLASS_NAME} />;
  }

  if (CODE_EXEC_TOOL_NAMES.has(normalizedToolName)) {
    return <CodeExecIcon className={ICON_CLASS_NAME} />;
  }

  if (CONTEXT7_TOOL_NAMES.has(normalizedToolName) || normalizedToolName.includes("context7")) {
    return <Context7Icon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "load_skill") {
    return <LoadSkillIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "shell") {
    return <ShellIcon className={ICON_CLASS_NAME} />;
  }

  if (normalizedToolName === "get_current_time") {
    return <TimeIcon className={ICON_CLASS_NAME} />;
  }

  const fileToolIcon = FILE_TOOL_ICONS[normalizedToolName];
  if (fileToolIcon) {
    const FileIcon = fileToolIcon;
    return <FileIcon className={ICON_CLASS_NAME} />;
  }

  return <ToolOutlined />;
}
