import XMarkdown from "@ant-design/x-markdown";
import Latex from "@ant-design/x-markdown/plugins/Latex";
import "@ant-design/x-markdown/themes/light.css";
import classNames from "classnames";
import React, { memo } from "react";
import CustomCodeBlock from "./components/CustomCodeBlock";
import { useMarkdownTheme } from "./hooks";
import styles from "./index.module.css";

type Props = {
  gray?: boolean;
  className?: string;
  style?: React.CSSProperties;
  children: string | undefined;
};

const MarkdownContainer = ({ children, gray, className, style: markdownStyle }: Props) => {
  const [markdownClassName] = useMarkdownTheme();

  if (!children) {
    return null;
  }

  return (
    <XMarkdown
      openLinksInNewTab
      components={{
        code: CustomCodeBlock,
      }}
      style={markdownStyle}
      config={{ extensions: [...Latex()] }}
      className={classNames(markdownClassName, styles["x-markdown"], gray && styles["gray"], className)}
    >
      {children}
    </XMarkdown>
  );
};

export default memo(MarkdownContainer);
