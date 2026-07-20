import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { parseToolArguments } from "../utils/parseToolArguments";
import { FileDiffView } from "./FileDiffView";

function getStringArg(args: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string") {
      return value;
    }
  }
  return undefined;
}

export function renderEditFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const filePath = getFilePathFromArgs(args);
  // argumentsText 流式阶段多为 snake_case；argumentsJson 经 camelcase 后为 camelCase
  const oldString = getStringArg(args, "oldString", "old_string");
  const newString = getStringArg(args, "newString", "new_string");
  // 流式中 new_string 可能尚未开始；有 old_string 即可先展示 diff
  if (typeof oldString !== "string" || !oldString) {
    return null;
  }

  const replaceAll = args.replaceAll === true || args.replace_all === true;

  return (
    <FileDiffView
      filePath={filePath}
      oldString={oldString}
      newString={newString ?? ""}
      replaceAll={replaceAll}
    />
  );
}
