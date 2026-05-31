import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";

export function renderWriteFileResult(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content;
  if (!content) {
    return null;
  }

  return (
    <Typography.Text type="secondary" className="text-sm">
      {content}
    </Typography.Text>
  );
}
