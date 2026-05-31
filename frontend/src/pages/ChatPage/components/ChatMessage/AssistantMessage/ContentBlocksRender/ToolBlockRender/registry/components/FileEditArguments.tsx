import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { parseToolArguments } from "../utils/parseToolArguments";
import { FileContentHighlight } from "./FileContentHighlight";

export function renderEditFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const filePath = getFilePathFromArgs(args);
  const oldString = args.old_string;
  const newString = args.new_string;
  if (typeof oldString !== "string" || !oldString || typeof newString !== "string") {
    return null;
  }

  const replaceAll = args.replace_all === true;
  const fileHeader = filePath && replaceAll ? `${filePath} · replace_all` : filePath;
  const oldHeader = fileHeader ? `${fileHeader} · old` : "old_string";

  return (
    <div className="w-full flex flex-col gap-2">
      <FileContentHighlight filePath={filePath} content={oldString} header={oldHeader} />
      <FileContentHighlight filePath={filePath} content={newString} header="new_string" />
    </div>
  );
}
