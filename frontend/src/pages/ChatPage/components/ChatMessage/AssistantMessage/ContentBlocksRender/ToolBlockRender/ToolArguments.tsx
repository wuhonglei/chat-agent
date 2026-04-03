import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Typography } from "antd";
import React, { useMemo, useState } from "react";

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
  const displayText = useMemo(() => {
    if (argumentsText) {
      return argumentsText;
    }
    if (!argumentsJson) {
      return "";
    }
    return JSON.stringify(argumentsJson, null, 2);
  }, [argumentsJson, argumentsText]);
  const executeCodeArgs = useMemo(() => {
    if (toolName !== "execute_code") {
      return null;
    }

    const parsedArguments = (() => {
      if (argumentsJson) {
        return argumentsJson;
      }
      if (!argumentsText) {
        return null;
      }
      try {
        return JSON.parse(argumentsText) as Record<string, unknown>;
      } catch {
        return null;
      }
    })();

    if (!parsedArguments) {
      return null;
    }

    const code = parsedArguments.code;
    if (typeof code !== "string" || !code) {
      return null;
    }
    const language = parsedArguments.language;
    return {
      code,
      language: typeof language === "string" && language ? language : "plaintext",
    };
  }, [argumentsJson, argumentsText, toolName]);

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
