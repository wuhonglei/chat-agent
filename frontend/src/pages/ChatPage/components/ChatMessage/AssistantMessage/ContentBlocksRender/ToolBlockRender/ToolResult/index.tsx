import type { ToolResultBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import React, { useMemo } from "react";

import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Divider } from "antd";
import { getResultLanguage, stringifyJsonLike } from "../utils";
import WebSearchResult from "./WebSearchResult";
import styles from "./index.module.css";

type ToolResultProps = {
  toolName?: string;
  toolResultBlock?: ToolResultBlock;
};

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

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

  if (toolName === "web_search" && searchDisplayItems?.length) {
    return <WebSearchResult items={searchDisplayItems} />;
  }

  if (toolName && ["web_pages_extract", "resolve-library-id", "query-docs"].includes(toolName)) {
    return (
      <>
        <Divider orientation="horizontal" style={{ margin: 0 }}></Divider>
        <MarkdownContainer style={containerStyle} className={styles["x-markdown"]}>
          {toolResultBlock.content}
        </MarkdownContainer>
      </>
    );
  }

  return (
    <CodeHighlighter
      lang={resultLanguage}
      header={"Result is"}
      styles={{
        code: containerStyle,
      }}
    >
      {stringifyJsonLike(toolResultBlock.content || "")}
    </CodeHighlighter>
  );
};

export default React.memo(ToolResult);
