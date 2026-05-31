import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";

export function renderWriteFileResult(ctx: ToolRenderContext): React.ReactNode | null {
  const { toolResultBlock } = ctx;
  if (!toolResultBlock) {
    return null;
  }

  if (!toolResultBlock.isError) {
    return <></>;
  }

  const content = toolResultBlock.content;
  if (!content) {
    return null;
  }

  return (
    <Typography.Text type="secondary" className="text-sm">
      {content}
    </Typography.Text>
  );
}
