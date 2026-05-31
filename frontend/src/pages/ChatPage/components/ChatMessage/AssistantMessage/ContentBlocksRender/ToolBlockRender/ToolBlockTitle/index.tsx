import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";
import React from "react";

import { STATUS_TITLE_MAP } from "./constants";
import { formatServerName } from "./formatServerName";
import { formatToolName } from "./utils";

type ToolBlockTitleProps = {
  serverName?: string;
  mcpToolName?: string;
  status: ContentBlockRenderStatus;
};

const ToolBlockTitle: React.FC<ToolBlockTitleProps> = ({ serverName, mcpToolName, status }) => {
  const displayToolName = formatToolName(mcpToolName || "");
  const displayServerName = formatServerName(serverName);
  const statusLabel = STATUS_TITLE_MAP[status] || "处理中";

  if (displayServerName) {
    return (
      <div className="flex items-center gap-1">
        <div>{displayServerName}</div>
        <div>·</div>
        <div>{displayToolName}</div>
        <div>·</div>
        <div>{statusLabel}</div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <div>{displayToolName}</div>
      <div>·</div>
      <div>{statusLabel}</div>
    </div>
  );
};

export default React.memo(ToolBlockTitle);
