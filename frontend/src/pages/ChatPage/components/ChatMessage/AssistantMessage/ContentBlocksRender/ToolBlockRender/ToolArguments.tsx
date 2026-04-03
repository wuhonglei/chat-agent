import { Typography } from "antd";
import React, { useState } from "react";

const { Paragraph } = Typography;

const DEFAULT_ELLIPSIS_ROWS = 10;

export type ToolArgumentsProps = {
  argumentsText: string;
  ellipsisRows?: number;
};

export const ToolArguments: React.FC<ToolArgumentsProps> = ({
  argumentsText,
  ellipsisRows = DEFAULT_ELLIPSIS_ROWS,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <Paragraph
      type="secondary"
      style={{ marginBottom: 0 }}
      ellipsis={{
        rows: ellipsisRows,
        expandable: "collapsible",
        expanded,
        symbol: isExpanded => (isExpanded ? "收起" : "展开"),
        onExpand: (_event, info) => setExpanded(info.expanded),
      }}
    >
      {argumentsText}
    </Paragraph>
  );
};

export default React.memo(ToolArguments);
