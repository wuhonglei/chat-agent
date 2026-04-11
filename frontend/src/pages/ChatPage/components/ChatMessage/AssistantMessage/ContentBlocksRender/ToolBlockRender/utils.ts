import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";

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
