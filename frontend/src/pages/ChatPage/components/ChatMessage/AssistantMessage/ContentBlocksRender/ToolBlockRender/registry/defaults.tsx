import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import React from "react";

import { stringifyJsonLike } from "../utils";
import { getFilePathFromArgs, getLanguageFromFilePath } from "./utils/filePathLanguage";
import type { ToolRenderContext, ToolRenderer } from "./types";

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

function getDefaultResultLanguage(ctx: ToolRenderContext): string {
  const filePath = getFilePathFromArgs(ctx.toolUseBlock.argumentsJson);
  if (filePath) {
    const languageFromPath = getLanguageFromFilePath(filePath);
    if (languageFromPath) {
      return languageFromPath;
    }
  }

  const content = ctx.toolResultBlock?.content || "";
  try {
    JSON.parse(content);
    return "json";
  } catch {
    return "markdown";
  }
}

export function renderDefaultToolResult(ctx: ToolRenderContext): React.ReactNode {
  const resultLanguage = getDefaultResultLanguage(ctx);
  return (
    <div className="w-full flex flex-col gap-2">
      <CodeHighlighter
        lang={resultLanguage}
        header="Result is"
        styles={{
          code: containerStyle,
        }}
      >
        {stringifyJsonLike(ctx.toolResultBlock?.content || "")}
      </CodeHighlighter>
    </div>
  );
}

export const DEFAULT_TOOL_RENDERER: ToolRenderer = {
  getResultLanguage: getDefaultResultLanguage,
  renderResult: renderDefaultToolResult,
};
