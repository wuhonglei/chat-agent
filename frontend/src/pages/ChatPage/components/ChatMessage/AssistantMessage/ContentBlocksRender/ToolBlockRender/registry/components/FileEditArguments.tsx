import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { parseToolArguments } from "../utils/parseToolArguments";
import { FileDiffView } from "./FileDiffView";

export function renderEditFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const filePath = getFilePathFromArgs(args);
  const oldString = args.oldString;
  const newString = args.newString;
  if (typeof oldString !== "string" || !oldString || typeof newString !== "string") {
    return null;
  }

  const replaceAll = args.replaceAll === true;

  return (
    <FileDiffView
      filePath={filePath}
      oldString={oldString}
      newString={newString}
      replaceAll={replaceAll}
    />
  );
}
