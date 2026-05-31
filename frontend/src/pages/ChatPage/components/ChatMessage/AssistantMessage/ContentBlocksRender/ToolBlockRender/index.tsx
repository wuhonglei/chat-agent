import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import { Think } from "@ant-design/x";
import React, { useMemo } from "react";

import ToolArguments from "./ToolArguments";
import ToolBlockTitle from "./ToolBlockTitle";
import ToolResult from "./ToolResult";
import { useToolBlockExpanded } from "./hooks";
import { resolveToolContext, resolveToolRenderer } from "./registry";
import type { ToolRenderContext } from "./registry/types";
import { isActiveStatus } from "./utils";

type Props = {
  toolUseBlock: ToolUseBlock;
  toolResultBlock?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

export const ToolBlockRender: React.FC<Props> = ({ toolUseBlock, toolResultBlock, status }) => {
  const { expanded, onExpandChange } = useToolBlockExpanded(status);
  const { serverName, mcpToolName } = resolveToolContext(toolUseBlock);
  const renderer = useMemo(
    () => resolveToolRenderer(serverName, mcpToolName),
    [mcpToolName, serverName]
  );

  console.info('renderer', renderer)

  const renderContext: ToolRenderContext = useMemo(
    () => ({
      serverName,
      mcpToolName,
      toolUseBlock,
      toolResultBlock,
      status,
    }),
    [mcpToolName, serverName, status, toolResultBlock, toolUseBlock]
  );

  return (
    <Think
      expanded={expanded}
      onExpand={onExpandChange}
      blink={isActiveStatus(status)}
      icon={renderer.icon}
      classNames={{ status: "cursor-pointer" }}
      title={<ToolBlockTitle serverName={serverName} mcpToolName={mcpToolName} status={status} />}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <ToolArguments renderContext={renderContext} renderer={renderer} />
        <ToolResult renderContext={renderContext} renderer={renderer} />
      </div>
    </Think>
  );
};

export default React.memo(ToolBlockRender);
