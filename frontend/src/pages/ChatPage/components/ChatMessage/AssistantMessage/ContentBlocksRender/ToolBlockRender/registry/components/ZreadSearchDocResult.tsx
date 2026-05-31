import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Divider } from "antd";
import React from "react";

import styles from "../../ToolResult/index.module.css";
import type { ToolRenderContext } from "../types";
import { unwrapZreadToolContent } from "../utils/zreadContent";

const containerStyle = { maxHeight: 480, width: "100%", overflow: "auto" };

export function renderZreadSearchDocResult(ctx: ToolRenderContext): React.ReactNode | null {
  const raw = ctx.toolResultBlock?.content;
  if (!raw?.trim()) {
    return null;
  }

  const markdown = unwrapZreadToolContent(raw);
  if (!markdown.trim()) {
    return null;
  }

  return (
    <>
      <Divider orientation="horizontal" style={{ margin: 0 }} />
      <MarkdownContainer style={containerStyle} className={styles["x-markdown"]}>
        {markdown}
      </MarkdownContainer>
    </>
  );
}
