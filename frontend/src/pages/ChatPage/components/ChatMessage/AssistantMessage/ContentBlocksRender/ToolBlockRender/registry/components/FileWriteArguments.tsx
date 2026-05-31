import { isPlainObject } from "lodash-es";
import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { FileContentHighlight } from "./FileContentHighlight";

function parseToolArguments(ctx: ToolRenderContext): Record<string, unknown> | null {
  const { argumentsJson, argumentsText } = ctx.toolUseBlock;
  if (isPlainObject(argumentsJson)) {
    return argumentsJson;
  }
  if (!argumentsText) {
    return null;
  }
  try {
    return JSON.parse(argumentsText) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function renderWriteFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const filePath = getFilePathFromArgs(args);
  const content = args.content;
  if (typeof content !== "string" || !content) {
    return null;
  }

  const append = args.append === true;
  const header = filePath && append ? `${filePath} · append` : filePath;

  return <FileContentHighlight filePath={filePath} content={content} header={header} />;
}
