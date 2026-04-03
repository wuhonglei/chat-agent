import { Typography } from "antd";
import React, { useMemo, useState } from "react";

const { Paragraph } = Typography;

const DEFAULT_ELLIPSIS_ROWS = 10;

export type ToolArgumentsProps = {
  argumentsText: string;
  argumentsJson?: Record<string, unknown>;
  ellipsisRows?: number;
};

export const ToolArguments: React.FC<ToolArgumentsProps> = ({
  argumentsText,
  argumentsJson,
  ellipsisRows = DEFAULT_ELLIPSIS_ROWS,
}) => {
  const [expanded, setExpanded] = useState(false);
  const displayText = useMemo(() => {
    if (argumentsText) {
      return argumentsText;
    }
    if (!argumentsJson) {
      return "";
    }
    return JSON.stringify(argumentsJson, null, 2);
  }, [argumentsJson, argumentsText]);

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
      {displayText}
    </Paragraph>
  );
};

export default React.memo(ToolArguments);
