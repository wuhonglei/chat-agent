import React, { memo, useRef } from "react";
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

import GrayContainer, { LanguageLabel } from "./components/GrayContainer";
import { Popover } from "antd";
import RoundTag from "@/components/common/RoundTag";

import classNames from "classnames";
import SourceCard from "../SourceSider/SourceCard";
import { SearchSource } from "@/types";
import CopyButton from "@/components/common/CopyButton";
import { useLanguage } from "./hooks";

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
      return <MermaidBlock code={code} />;
    }

    return (
      <GrayContainer
        header={
          <>
            <LanguageLabel children={language} />
            <CopyButton text={code} />
          </>
        }
      >
        <NormalCode language={language}>{code}</NormalCode>
      </GrayContainer>
    );
  }
);

const CustomSup = memo(
  ({
    children,
    sources,
  }: {
    children?: React.ReactNode;
    sources: SearchSource[] | undefined;
  }) => {
    // 检查 children 是否是 React 元素并且有 props
    const href = (children as React.ReactElement)?.props?.href || "";
    const isCite = href.startsWith("#user-content-fn-cite:");
    const tagRef = useRef(null);

    if (!isCite) {
      return React.createElement("sup", {}, children);
    }

    const index = Number(href.split("#user-content-fn-cite:")[1]);

    return (
      <Popover
        styles={{
          body: {
            padding: 0,
            width: 400,
          },
        }}
        content={
          <SourceCard
            rank={index}
            hoverable={false}
            source={sources?.[index - 1]}
          />
        }
        getPopupContainer={() => tagRef.current || document.body}
      >
        <RoundTag
          ref={tagRef}
          interactive
          onClick={() => {
            window.open(sources?.[index - 1]?.url, "_blank");
          }}
        >
          {index}
        </RoundTag>
      </Popover>
    );
  }
);

type Props = {
  className?: string;
  sources?: SearchSource[];
  children: string | undefined;
};

const MarkdownContainer = ({ children, className, sources }: Props) => {
  const SupComponent = React.useCallback(
    (props: any) => <CustomSup {...props} sources={sources} />,
    [sources]
  );

  if (!children) {
    return null;
  }

  return (
    <ReactMarkdown
      components={{
        code: CustomCodeBlock,
        sup: SupComponent,
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
