import { WeatherNow } from "@/pages/ChatPage/components/MarkdownContainer/code_components/Weather";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Mermaid } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import Latex from "@ant-design/x-markdown/plugins/Latex";
import classNames from "classnames";
import { jsonrepair } from "jsonrepair";
import React, { memo } from "react";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import InlineCode from "./components/InlineCode";
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
      return <InlineCode>{code}</InlineCode>;
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

    if (language === "component_weather") {
      try {
        const parsedData = JSON.parse(jsonrepair(code));
        return React.createElement(WeatherNow, parsedData);
      } catch (error) {
        // JSON 解析失败时，降级为代码高亮展示
        console.warn("天气组件 JSON 解析失败，降级为代码展示:", error);
        return <CodeHighlighter lang="json">{code}</CodeHighlighter>;
      }
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
