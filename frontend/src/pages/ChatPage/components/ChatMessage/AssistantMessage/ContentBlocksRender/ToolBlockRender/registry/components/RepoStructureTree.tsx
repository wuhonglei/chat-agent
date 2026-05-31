import React from "react";

import type { ToolRenderContext } from "../types";
import { formatZreadRepoStructureDisplay } from "../utils/zreadContent";

export function renderRepoStructureTree(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content?.trim();
  if (!content) {
    return null;
  }

  const display = formatZreadRepoStructureDisplay(content);
  if (!display) {
    return null;
  }

  return (
    <div className="w-full rounded border border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) p-3">
      <pre className="mb-0 max-h-[480px] overflow-auto whitespace-pre-wrap font-mono text-sm leading-relaxed">
        {display}
      </pre>
    </div>
  );
}
