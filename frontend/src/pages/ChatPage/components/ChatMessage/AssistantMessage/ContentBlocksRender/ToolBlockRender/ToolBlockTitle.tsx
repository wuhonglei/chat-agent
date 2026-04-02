import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";
import React from "react";

import { STATUS_TITLE_MAP } from "./constants";
import { formatToolName } from "./utils";

type ToolBlockTitleProps = {
  rawToolName?: string;
  status: ContentBlockRenderStatus;
};

const ToolBlockTitle: React.FC<ToolBlockTitleProps> = ({ rawToolName, status }) => {
  const displayToolName = formatToolName(rawToolName || "");
  return (
    <div className="text-sm text-gray-500 cursor-pointer">{`${displayToolName} · ${STATUS_TITLE_MAP[status] || "处理中"}`}</div>
  );
};

export default React.memo(ToolBlockTitle);
