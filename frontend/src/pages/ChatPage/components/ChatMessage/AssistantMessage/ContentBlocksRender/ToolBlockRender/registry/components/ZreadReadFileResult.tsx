import { Divider } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";
import { getFilePathFromArgs } from "../utils/filePathLanguage";
import { unwrapZreadToolContent } from "../utils/zreadContent";
import { FileContentHighlight } from "./FileContentHighlight";

export function renderZreadReadFileResult(ctx: ToolRenderContext): React.ReactNode | null {
  const raw = ctx.toolResultBlock?.content;
  if (!raw?.trim()) {
    return null;
  }

  const content = unwrapZreadToolContent(raw);
  if (!content.trim()) {
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
