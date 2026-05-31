import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Divider } from "antd";
import React from "react";

import styles from "../../ToolResult/index.module.css";
import type { ToolRenderContext } from "../types";

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

export function renderMarkdownToolResult(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content;
  if (!content) {
    return null;
  }

  return (
    <>
      <Divider orientation="horizontal" style={{ margin: 0 }} />
      <MarkdownContainer style={containerStyle} className={styles["x-markdown"]}>
        {content}
      </MarkdownContainer>
    </>
  );
}
