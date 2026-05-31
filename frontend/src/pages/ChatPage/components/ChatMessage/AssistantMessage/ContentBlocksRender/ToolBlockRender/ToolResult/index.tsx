import type { ToolRenderer } from "../registry/types";
import type { ToolRenderContext } from "../registry/types";
import { renderToolResult } from "../registry/resolveToolRenderer";
import React from "react";

type ToolResultProps = {
  renderContext: ToolRenderContext;
  renderer: ToolRenderer;
};

const ToolResult: React.FC<ToolResultProps> = ({ renderContext, renderer }) => {
  const { toolResultBlock } = renderContext;

  if (!toolResultBlock) {
    return null;
  }

  if (toolResultBlock.isError) {
    return (
      <div className="w-full flex items-start gap-2">
        <div className="whitespace-nowrap">tool call error.</div>
        {toolResultBlock.content ? <div>{toolResultBlock.content}</div> : null}
      </div>
    );
  }

  return <>{renderToolResult(renderContext, renderer)}</>;
};

export default React.memo(ToolResult);
