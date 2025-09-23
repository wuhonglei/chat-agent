import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeExternalLinks from "rehype-external-links";
import remarkMath from "remark-math";
import MermaidBlock from "./components/MermaidBlock";
import "katex/dist/katex.min.css";
import styles from "./index.module.css";
import InlineCode from "./components/InlineCode";
import NormalCode from "./components/NormalCode";

import GrayContainer, {
  LanguageLabel,
  CopyButton,
} from "./components/GrayContainer";
import { Popover } from "antd";
import RoundTag from "@/components/RoundTag";

import classNames from "classnames";

interface CustomCodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

const CustomCodeBlock = ({
  inline,
  className,
  children,
}: CustomCodeBlockProps) => {
  const match = /language-(\w+)/.exec(className || "");
  const code = String(children).replace(/\n$/, "");
  const language = match ? match[1] : "";

  // 处理 Mermaid 代码块
  if (!inline && language === "mermaid") {
    return <MermaidBlock code={code} />;
  }

  if (inline || !language) {
    return <InlineCode>{children}</InlineCode>;
  }

  return (
    <GrayContainer
      header={
        <>
          <LanguageLabel children={language} />
          <CopyButton children={code} />
        </>
      }
    >
      <NormalCode language={language}>{code}</NormalCode>
    </GrayContainer>
  );
};

const CustomSup = (props: { children: React.ReactNode | string }) => {
  const { children } = props;
  const href = children?.props?.href || "";
  const isCite = href.startsWith("#user-content-fn-cite:");

  if (!isCite) {
    return React.createElement("sup", {}, children);
  }

  const index = href.split("#user-content-fn-cite:")[1];

  return (
    <Popover content={index}>
      <RoundTag interactive>{index}</RoundTag>
    </Popover>
  );
};

type Props = {
  children: string | undefined;
  className?: string;
};

const MarkdownContainer = ({ children, className }: Props) => {
  if (!children) {
    return null;
  }

  return (
    <ReactMarkdown
      components={{
        code: CustomCodeBlock,
        sup: CustomSup,
      }}
      rehypePlugins={[
        rehypeRaw,
        rehypeKatex,
        [
          rehypeExternalLinks,
          {
            target: "_blank",
            rel: ["noopener", "noreferrer"],
          },
        ],
      ]} // HTML 生成阶段, 处理已转换的 HTML 树，在渲染前进行最终处理
      remarkPlugins={[[remarkGfm], remarkMath]} // Markdown 解析阶段, 处理原始 Markdown 文本，转换成 AST（抽象语法树）
      className={classNames(styles["markdown-body"], className)}
    >
      {children}
    </ReactMarkdown>
  );
};

export default memo(MarkdownContainer);
