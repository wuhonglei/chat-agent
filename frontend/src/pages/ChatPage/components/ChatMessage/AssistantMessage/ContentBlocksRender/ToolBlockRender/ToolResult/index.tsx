import type { ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { useBlockPreview } from "@/pages/ChatPage/context/BlockPreviewContext";
import { Button, Divider } from "antd";
import React from "react";
import { useParams } from "react-router-dom";

import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { stringifyJsonLike } from "../utils";
import { useCanOpenProjectPreview, useToolResultLanguage } from "./hooks";
import WebSearchResult from "./WebSearchResult";
import styles from "./index.module.css";

type ToolResultProps = {
  toolName?: string;
  toolResultBlock?: ToolResultBlock;
  toolUseBlock?: ToolUseBlock;
};

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

const ToolResult: React.FC<ToolResultProps> = ({ toolName, toolResultBlock, toolUseBlock }) => {
  const blockPreview = useBlockPreview();
  const params = useParams<{ conversationId: string }>();
  const currentToolName = toolName ?? toolUseBlock?.name;
  const resultLanguage = useToolResultLanguage({
    currentToolName,
    toolResultBlock,
    toolUseBlock,
  });
  const searchDisplayItems = toolResultBlock?.structuredContentForDisplay;
  const canOpenProjectPreview = useCanOpenProjectPreview({
    toolResultBlock,
    currentToolName,
    conversationId: params.conversationId,
  });

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
      {canOpenProjectPreview ? (
        <div>
          <Button
            size="small"
            onClick={() => {
              if (!blockPreview || !params.conversationId) {
                return;
              }
              blockPreview.openPreview({
                id: `cb_project_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                type: "project",
                workspaceId: params.conversationId,
                title: "项目结构预览",
              });
            }}
          >
            打开项目结构预览
          </Button>
        </div>
      ) : null}
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
