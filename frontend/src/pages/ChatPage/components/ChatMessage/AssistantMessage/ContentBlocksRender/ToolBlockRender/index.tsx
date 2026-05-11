import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import { Think } from "@ant-design/x";
import React from "react";

import ToolArguments from "./ToolArguments";
import ToolBlockTitle from "./ToolBlockTitle";
import ToolResult from "./ToolResult";
import { useToolBlockExpanded } from "./hooks";
import { getToolIcon } from "./toolIcons";
import { isActiveStatus } from "./utils";

type Props = {
  toolUseBlock: ToolUseBlock;
  toolResultBlock?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

export const ToolBlockRender: React.FC<Props> = ({ toolUseBlock, toolResultBlock, status }) => {
  const { expanded, onExpandChange } = useToolBlockExpanded(status);

  return (
    <Think
      icon={getToolIcon(toolUseBlock.name)}
      expanded={expanded}
      blink={isActiveStatus(status)}
      onExpand={onExpandChange}
      classNames={{ status: "cursor-pointer" }}
      title={<ToolBlockTitle rawToolName={toolUseBlock.name} status={status} />}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <ToolArguments
          toolName={toolUseBlock.name}
          argumentsText={toolUseBlock.argumentsText}
          argumentsJson={toolUseBlock.argumentsJson}
        />
        <ToolResult toolName={toolUseBlock.name} toolResultBlock={toolResultBlock} toolUseBlock={toolUseBlock} />
      </div>
    </Think>
  );
};

export default React.memo(ToolBlockRender);
