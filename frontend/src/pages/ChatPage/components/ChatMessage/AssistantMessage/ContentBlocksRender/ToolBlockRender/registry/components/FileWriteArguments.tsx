import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { parseToolArguments } from "../utils/parseToolArguments";
import { FileContentHighlight } from "./FileContentHighlight";

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
