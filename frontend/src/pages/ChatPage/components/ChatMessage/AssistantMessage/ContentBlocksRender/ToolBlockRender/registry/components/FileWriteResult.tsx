import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";

const FILE_WRITTEN_PATTERN = /^File written:\s*.+$/;

export function renderWriteFileResult(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content?.trim();
  if (!content) {
    return null;
  }

  const message = FILE_WRITTEN_PATTERN.test(content) ? "文件已写入" : content;

  return (
    <Typography.Text type="secondary" className="text-sm">
      {message}
    </Typography.Text>
  );
}
