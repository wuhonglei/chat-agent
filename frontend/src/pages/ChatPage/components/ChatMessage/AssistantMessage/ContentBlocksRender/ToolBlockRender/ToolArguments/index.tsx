import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Typography } from "antd";
import React, { useState } from "react";

import { useExecuteCodeToolArguments, useToolArgumentsDisplayText } from "./hooks";

const { Paragraph } = Typography;

const DEFAULT_ELLIPSIS_ROWS = 10;

export type ToolArgumentsProps = {
  toolName?: string;
  argumentsText: string;
  argumentsJson?: Record<string, unknown>;
  ellipsisRows?: number;
};

export const ToolArguments: React.FC<ToolArgumentsProps> = ({
  toolName,
  argumentsText,
  argumentsJson,
  ellipsisRows = DEFAULT_ELLIPSIS_ROWS,
}) => {
  const [expanded, setExpanded] = useState(false);
  const displayText = useToolArgumentsDisplayText(argumentsText, argumentsJson);
  const executeCodeArgs = useExecuteCodeToolArguments(toolName, argumentsText, argumentsJson);

  if (executeCodeArgs) {
    return (
      <CodeHighlighter
        lang={executeCodeArgs.language}
        styles={{
          code: { width: "100%", overflow: "auto" },
        }}
      >
        {executeCodeArgs.code}
      </CodeHighlighter>
    );
  }

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
