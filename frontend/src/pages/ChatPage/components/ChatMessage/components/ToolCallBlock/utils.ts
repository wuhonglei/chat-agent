import { ToolResultSuccessTimelineMessage } from "@/interfaces";
import { prettyCount } from "@/utils";
import { isPlainObject } from "lodash-es";

export function stringifyArgs(args: string): string {
  if (!args) {
    return "";
  }

  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

export function stringifyContentWithLanguage<
  T extends string | Record<string, unknown>,
>(content: T | undefined): [string, string] {
  if (!content) {
    return ["", ""];
  }

  if (isPlainObject(content)) {
    return [JSON.stringify(content, null, 2), "json"];
  }

  try {
    const str = JSON.stringify(JSON.parse(content as string), null, 2);
    return [str, "json"];
  } catch {
    return [content as string, "markdown"];
  }
}

export function getContentTokenCountDesc(
  message: ToolResultSuccessTimelineMessage
): string {
  const { contentTokenCount, originalTokenCount, relevanceApplied } = message;
  if (relevanceApplied && originalTokenCount && contentTokenCount) {
    return ` (${prettyCount(originalTokenCount)} tokens) -> (${prettyCount(contentTokenCount)} tokens)`;
  } else if (contentTokenCount) {
    return ` (${prettyCount(contentTokenCount)} tokens)`;
  }
  return "";
}
