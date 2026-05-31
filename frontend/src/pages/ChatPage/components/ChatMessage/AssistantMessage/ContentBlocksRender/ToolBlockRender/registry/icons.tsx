import CodeIcon from "@/assets/svg/mcp-tools/code.svg?react";
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
import ZreadIcon from "@/assets/svg/mcp-tools/zread.svg?react";
import { ToolOutlined } from "@ant-design/icons";
import React from "react";

export const ICON_CLASS_NAME = "w-4 h-4";

export function renderIcon(Icon: React.ComponentType<{ className?: string }>): React.ReactNode {
  return <Icon className={ICON_CLASS_NAME} />;
}

export const DEFAULT_ICON = <ToolOutlined className={ICON_CLASS_NAME} />;

export {
  CodeIcon,
  Context7Icon,
  EditFileIcon,
  LoadSkillIcon,
  PresentFilesIcon,
  ReadFileIcon,
  SearchFilesIcon,
  ShellIcon,
  TimeIcon,
  WeatherIcon,
  WebCrawlIcon,
  WebExtractIcon,
  WebResearchIcon,
  WebSearchIcon,
  WriteFileIcon,
  ZreadIcon,
};
