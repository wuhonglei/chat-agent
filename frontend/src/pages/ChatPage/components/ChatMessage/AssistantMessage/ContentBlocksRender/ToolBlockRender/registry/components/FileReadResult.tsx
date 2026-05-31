import { Divider } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { FileContentHighlight } from "./FileContentHighlight";

export function renderFileReadResult(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content;
  if (!content) {
    return null;
  }

  const filePath = getFilePathFromArgs(ctx.toolUseBlock.argumentsJson);

  return (
    <>
      <Divider orientation="horizontal" style={{ margin: 0 }} />
      <div className="w-full flex flex-col gap-2">
        <FileContentHighlight filePath={filePath} content={content} />
      </div>
    </>
  );
}
