import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { theme, Typography } from "antd";
import classNames from "classnames";
import React, { useState } from "react";

import type { ToolRenderContext } from "../registry/types";
import type { ToolRenderer } from "../registry/types";
import { useToolArgumentsDisplay } from "./hooks";
import styles from "./index.module.css";

const { Paragraph } = Typography;

const DEFAULT_ELLIPSIS_ROWS = 10;

export type ToolArgumentsProps = {
  renderContext: ToolRenderContext;
  renderer: ToolRenderer;
};

export const ToolArguments: React.FC<ToolArgumentsProps> = ({ renderContext, renderer }) => {
  const { token } = theme.useToken();
  const [expanded, setExpanded] = useState(false);
  const { toolUseBlock } = renderContext;

  const customArguments = renderer.renderArguments?.(renderContext);
  if (customArguments != null) {
    return <>{customArguments}</>;
  }

  const { markdown, plain } = useToolArgumentsDisplay(
    toolUseBlock.argumentsText,
    toolUseBlock.argumentsJson
  );

  if (markdown) {
    return (
      <MarkdownContainer
        style={{ color: token.colorTextSecondary }}
        className={classNames("text-sm w-full", styles.markdown)}
      >
        {markdown}
      </MarkdownContainer>
    );
  }

  return (
    <Paragraph
      type="secondary"
      style={{ marginBottom: 0 }}
      ellipsis={{
        rows: DEFAULT_ELLIPSIS_ROWS,
        expandable: "collapsible",
        expanded,
        symbol: isExpanded => (isExpanded ? "收起" : "展开"),
        onExpand: (_event, info) => setExpanded(info.expanded),
      }}
    >
      {plain}
    </Paragraph>
  );
};

export default React.memo(ToolArguments);
