import type { ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Divider } from "antd";
import React from "react";

import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { stringifyJsonLike } from "../utils";
import { useToolResultLanguage } from "./hooks";
import WebSearchResult from "./WebSearchResult";
import styles from "./index.module.css";

type ToolResultProps = {
  toolName?: string;
  toolResultBlock?: ToolResultBlock;
  toolUseBlock?: ToolUseBlock;
};

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

const ToolResult: React.FC<ToolResultProps> = ({ toolName, toolResultBlock, toolUseBlock }) => {
  const currentToolName = toolName ?? toolUseBlock?.name;
  const resultLanguage = useToolResultLanguage({
    currentToolName,
    toolResultBlock,
    toolUseBlock,
  });
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

  if (currentToolName === "web_search" && searchDisplayItems?.length) {
    return <WebSearchResult items={searchDisplayItems} />;
  }

  if (
    currentToolName &&
    ["web_pages_extract", "resolve-library-id", "query-docs", "load_skill"].includes(currentToolName)
  ) {
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
    <div className="w-full flex flex-col gap-2">
      <CodeHighlighter
        lang={resultLanguage}
        header={"Result is"}
        styles={{
          code: containerStyle,
        }}
      >
        {stringifyJsonLike(toolResultBlock.content || "")}
      </CodeHighlighter>
    </div>
  );
};

export default React.memo(ToolResult);
