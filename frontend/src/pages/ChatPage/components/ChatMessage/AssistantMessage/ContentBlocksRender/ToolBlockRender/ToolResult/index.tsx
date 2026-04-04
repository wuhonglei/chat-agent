import type { ToolResultBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import React, { useMemo } from "react";

import { getResultLanguage, stringifyJsonLike } from "../utils";
import WebSearchResult from "./WebSearchResult";

const WEB_SEARCH_TOOL_NAME = "web_search";

type ToolResultProps = {
  toolName?: string;
  toolResultBlock?: ToolResultBlock;
};

const ToolResult: React.FC<ToolResultProps> = ({ toolName, toolResultBlock }) => {
  const resultLanguage = useMemo(() => getResultLanguage(toolResultBlock?.content || ""), [toolResultBlock?.content]);
  const searchDisplayItems = toolResultBlock?.structuredContentForDisplay;

  if (!toolResultBlock) {
    return null;
  }

  if (toolResultBlock.isError) {
    return (
      <div className="w-full flex items-start gap-2">
        <div className="whitespace-nowrap">tool call error.</div>
        {toolResultBlock.content ? <div>{toolResultBlock.content}</div> : null}
      </div>
    );
  }

  if (toolName === WEB_SEARCH_TOOL_NAME && searchDisplayItems?.length) {
    return <WebSearchResult items={searchDisplayItems} />;
  }

  return (
    <CodeHighlighter
      lang={resultLanguage}
      header={"Result is"}
      styles={{
        code: { maxHeight: 300, width: "100%", overflow: "auto" },
      }}
    >
      {stringifyJsonLike(toolResultBlock.content || "")}
    </CodeHighlighter>
  );
};

export default React.memo(ToolResult);
