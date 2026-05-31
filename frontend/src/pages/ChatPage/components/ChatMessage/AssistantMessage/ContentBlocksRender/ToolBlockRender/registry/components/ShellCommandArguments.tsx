import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { trim } from "lodash-es";
import React from "react";

import type { ToolRenderContext } from "../types";

export function renderShellCommandArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const command = ctx.toolUseBlock.argumentsJson?.command;
  if (typeof command !== "string" || !command.trim()) {
    return null;
  }

  return (
    <CodeHighlighter lang="bash" styles={{ code: { width: "100%", overflow: "auto" } }}>
      {trim(command)}
    </CodeHighlighter>
  );
}
