import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Mermaid } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import Latex from "@ant-design/x-markdown/plugins/Latex";
import classNames from "classnames";
import React, { memo } from "react";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useLanguage, useMarkdownTheme } from "./hooks";
import "./index.css";
import styles from "./index.module.css";

interface CustomCodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

const CustomCodeBlock = memo(
  ({ inline, className, children }: CustomCodeBlockProps) => {
    const code = String(children).replace(/\n$/, "");
    const language = useLanguage(className, code, inline);

    if (inline || !language) {
      return <CodeHighlighter>{code}</CodeHighlighter>;
    }

    // 处理 Mermaid 代码块
    if (language === "mermaid") {
      return (
        <Mermaid
          styles={{ graph: { backgroundColor: "#f8f9fa" } }}
          highlightProps={{
            customStyle: {},
            style: oneLight,
          }}
        >
          {code}
        </Mermaid>
      );
    }

    return <CodeHighlighter lang={language}>{code}</CodeHighlighter>;
  }
);

type Props = {
  gray?: boolean;
  className?: string;
  styles?: React.CSSProperties;
  children: string | undefined;
};

const MarkdownContainer = ({
  children,
  gray,
  className,
  styles: markdownStyles,
}: Props) => {
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
      style={markdownStyles}
      config={{ extensions: [...Latex()] }}
      className={classNames(
        markdownClassName,
        styles["x-markdown"],
        gray && styles["gray"],
        className
      )}
    >
      {children}
    </XMarkdown>
  );
};

export default memo(MarkdownContainer);
