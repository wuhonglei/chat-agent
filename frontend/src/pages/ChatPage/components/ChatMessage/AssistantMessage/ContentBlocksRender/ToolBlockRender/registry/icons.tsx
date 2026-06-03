// oxlint-disable react/only-export-components -- MCP tool icon registry mixes SVG nodes with lookup helpers
import CodeIcon from "@/assets/svg/mcp-tools/code.svg?react";
import Context7Icon from "@/assets/svg/mcp-tools/context7.svg?react";
import EditFileIcon from "@/assets/svg/mcp-tools/edit-file.svg?react";
import LoadSkillIcon from "@/assets/svg/mcp-tools/load-skill.svg?react";
import PresentFilesIcon from "@/assets/svg/mcp-tools/present-files.svg?react";
import ReadFileIcon from "@/assets/svg/mcp-tools/read-file.svg?react";
import RepoStructureIcon from "@/assets/svg/mcp-tools/repo-structure.svg?react";
import SearchFilesIcon from "@/assets/svg/mcp-tools/search-files.svg?react";
import ShellIcon from "@/assets/svg/mcp-tools/shell.svg?react";
import TimeIcon from "@/assets/svg/mcp-tools/time.svg?react";
import WeatherIcon from "@/assets/svg/mcp-tools/weather.svg?react";
import WebCrawlIcon from "@/assets/svg/mcp-tools/web-crawl.svg?react";
import WebExtractIcon from "@/assets/svg/mcp-tools/web-extract.svg?react";
import WebResearchIcon from "@/assets/svg/mcp-tools/web-research.svg?react";
import WebSearchIcon from "@/assets/svg/mcp-tools/web-search.svg?react";
import WriteFileIcon from "@/assets/svg/mcp-tools/write-file.svg?react";
import ZreadReadFileIcon from "@/assets/svg/mcp-tools/zread-read-file.svg?react";
import ZreadSearchDocIcon from "@/assets/svg/mcp-tools/zread-search-doc.svg?react";
import { ToolOutlined } from "@ant-design/icons";
import React from "react";

export const ICON_CLASS_NAME = "w-4 h-4";

export function renderIcon(Icon: React.ComponentType<{ className?: string }>): React.ReactNode {
  return <Icon className={ICON_CLASS_NAME} />;
}

export const DEFAULT_ICON = <ToolOutlined className={ICON_CLASS_NAME} />;

const codeIcon = renderIcon(CodeIcon);
const context7Icon = renderIcon(Context7Icon);
const shellIcon = renderIcon(ShellIcon);
const loadSkillIcon = renderIcon(LoadSkillIcon);
const timeIcon = renderIcon(TimeIcon);
const weatherIcon = renderIcon(WeatherIcon);

/** MCP tool icons keyed by server name and tool name (matches backend mcp_servers config). */
export const SERVER_TOOL_ICONS: Record<string, Record<string, React.ReactNode>> = {
  tavily: {
    web_search: renderIcon(WebSearchIcon),
    web_pages_extract: renderIcon(WebExtractIcon),
    web_site_crawl: renderIcon(WebCrawlIcon),
    web_site_map: renderIcon(WebResearchIcon),
    research: renderIcon(WebResearchIcon),
  },
  file: {
    read_file: renderIcon(ReadFileIcon),
    write_file: renderIcon(WriteFileIcon),
    edit_file: renderIcon(EditFileIcon),
    search_files: renderIcon(SearchFilesIcon),
    present_files: renderIcon(PresentFilesIcon),
  },
  code: {
    execute_code: codeIcon,
    list_runtimes: codeIcon,
  },
  shell: {
    shell: shellIcon,
  },
  skill_manager: {
    load_skill: loadSkillIcon,
  },
  context7: {
    "resolve-library-id": context7Icon,
    "query-docs": context7Icon,
  },
  weather: {
    search_city: weatherIcon,
    get_current_weather: weatherIcon,
    get_weather_hourly_forecast: weatherIcon,
    get_weather_daily_forecast: weatherIcon,
    get_weather_alerts: weatherIcon,
  },
  time: {
    get_current_time: timeIcon,
  },
  zread: {
    get_repo_structure: renderIcon(RepoStructureIcon),
    read_file: renderIcon(ZreadReadFileIcon),
    search_doc: renderIcon(ZreadSearchDocIcon),
  },
};

export function lookupToolIcon(
  serverName: string | undefined,
  mcpToolName: string,
  fallback: React.ReactNode = DEFAULT_ICON,
): React.ReactNode {
  if (!serverName) {
    return fallback;
  }
  return SERVER_TOOL_ICONS[serverName]?.[mcpToolName] ?? fallback;
}

/** @alias lookupToolIcon */
export const lookUpIcon = lookupToolIcon;
