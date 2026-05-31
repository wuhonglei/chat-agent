import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { trim } from "lodash-es";
import React from "react";

import type { ToolRenderContext } from "../types";

export function renderExecuteCodeArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const { toolUseBlock } = ctx;
  const parsedArguments = toolUseBlock.argumentsJson ?? parseArgumentsJson(toolUseBlock.argumentsText);
  if (!parsedArguments) {
    return null;
  }

  const code = parsedArguments.code;
  if (typeof code !== "string" || !code) {
    return null;
  }

  const language = parsedArguments.language;
  return (
    <CodeHighlighter
      lang={typeof language === "string" && language ? language : "python"}
      styles={{ code: { width: "100%", overflow: "auto" } }}
    >
      {trim(code)}
    </CodeHighlighter>
  );
}

function parseArgumentsJson(argumentsText: string): Record<string, unknown> | null {
  if (!argumentsText) {
    return null;
  }
  try {
    return JSON.parse(argumentsText) as Record<string, unknown>;
  } catch {
    return null;
  }
}
