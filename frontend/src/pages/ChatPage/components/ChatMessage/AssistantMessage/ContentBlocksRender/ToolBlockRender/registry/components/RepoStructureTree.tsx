import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";
import { formatZreadRepoStructureDisplay } from "../utils/zreadContent";

export function renderRepoStructureTree(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content?.trim();
  if (!content) {
    return null;
  }

  const formatted = formatZreadRepoStructureDisplay(content);
  if (!formatted) {
    return null;
  }

  return (
    <div className="w-full rounded border border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) p-3">
      {formatted.title ? (
        <Typography.Text type="secondary" className="block text-sm">
          {formatted.title}
        </Typography.Text>
      ) : null}
      <pre className="mt-2 mb-0 max-h-[480px] overflow-auto whitespace-pre-wrap font-mono text-sm leading-relaxed">
        {formatted.body}
      </pre>
      {formatted.tip ? (
        <Typography.Text type="secondary" className="mt-2 block text-xs">
          {formatted.tip}
        </Typography.Text>
      ) : null}
    </div>
  );
}
