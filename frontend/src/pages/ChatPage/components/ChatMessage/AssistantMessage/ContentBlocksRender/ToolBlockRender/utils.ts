import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";
import { capitalize, words } from "lodash-es";

import { ACTIVE_STATUS_SET } from "./constants";

export function isActiveStatus(status: ContentBlockRenderStatus): boolean {
  return ACTIVE_STATUS_SET.has(status);
}

export function stringifyJsonLike(input: string): string {
  if (!input) {
    return "";
  }
  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch {
    return input;
  }
}

export function getResultLanguage(content: string): "json" | "markdown" {
  try {
    JSON.parse(content);
    return "json";
  } catch {
    return "markdown";
  }
}

export function formatToolName(name?: string): string {
  if (!name) {
    return "未知工具";
  }

  const formattedName = words(name).map(capitalize).join(" ");
  return formattedName || "未知工具";
}
