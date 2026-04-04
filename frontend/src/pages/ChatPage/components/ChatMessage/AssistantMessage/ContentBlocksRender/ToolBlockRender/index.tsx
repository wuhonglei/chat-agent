import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import { Think } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import React, { useEffect, useState } from "react";

import ToolArguments from "./ToolArguments";
import ToolBlockTitle from "./ToolBlockTitle";
import ToolResult from "./ToolResult";
import { getToolIcon } from "./toolIcons";
import { isActiveStatus } from "./utils";

type Props = {
  toolUseBlock: ToolUseBlock;
  toolResultBlock?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

export const ToolBlockRender: React.FC<Props> = ({ toolUseBlock, toolResultBlock, status }) => {
  const [expanded, setExpanded] = useState<boolean>(isActiveStatus(status));
  const handleExpandChange = useMemoizedFn((nextExpanded: boolean) => {
    setExpanded(nextExpanded);
  });

  useEffect(() => {
    if (isActiveStatus(status)) {
      setExpanded(true);
      return;
    }
    setExpanded(false);
  }, [status]);

  return (
    <Think
      icon={getToolIcon(toolUseBlock.name)}
      expanded={expanded}
      blink={isActiveStatus(status)}
      onExpand={handleExpandChange}
      classNames={{ status: "cursor-pointer" }}
      title={<ToolBlockTitle rawToolName={toolUseBlock.name} status={status} />}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <ToolArguments
          toolName={toolUseBlock.name}
          argumentsText={toolUseBlock.argumentsText}
          argumentsJson={toolUseBlock.argumentsJson}
        />
        <ToolResult toolName={toolUseBlock.name} toolResultBlock={toolResultBlock} />
      </div>
    </Think>
  );
};

export default React.memo(ToolBlockRender);
