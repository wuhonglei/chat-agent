import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { theme, Typography } from "antd";
import React, { useState } from "react";

import { useExecuteCodeToolArguments, useToolArgumentsDisplay } from "./hooks";

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
  const { token } = theme.useToken();
  const [expanded, setExpanded] = useState(false);

  const { markdown, plain } = useToolArgumentsDisplay(argumentsText, argumentsJson);
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

  if (markdown) {
    return (
      <MarkdownContainer className="text-sm w-full" style={{ color: token.colorTextSecondary }}>
        {markdown}
      </MarkdownContainer>
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
      {plain}
    </Paragraph>
  );
};

export default React.memo(ToolArguments);
