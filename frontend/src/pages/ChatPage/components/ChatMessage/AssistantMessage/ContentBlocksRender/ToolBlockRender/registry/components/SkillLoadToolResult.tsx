import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Divider } from "antd";
import React from "react";

import styles from "../../ToolResult/index.module.css";
import type { ToolRenderContext } from "../types";
import { parseSkillContent } from "./parseSkillContent";

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };
const preClassName =
  "m-0 whitespace-pre-wrap wrap-break-word font-mono text-xs text-(--ant-color-text-secondary)";

export function renderSkillLoadToolResult(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content;
  if (!content) {
    return null;
  }

  const parsed = parseSkillContent(content);

  return (
    <>
      <Divider orientation="horizontal" style={{ margin: 0 }} />
      <div className="w-full space-y-2 p-2" style={containerStyle}>
        {parsed ? (
          <>
            <pre className={preClassName}>{parsed.prefix}</pre>
            {parsed.body ? (
              <MarkdownContainer className={styles["x-markdown"]}>{parsed.body}</MarkdownContainer>
            ) : null}
            <pre className={preClassName}>{parsed.suffix}</pre>
          </>
        ) : (
          <pre className={preClassName}>{content}</pre>
        )}
      </div>
    </>
  );
}
