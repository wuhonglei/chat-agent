import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeExternalLinks from "rehype-external-links";
import remarkMath from "remark-math";
import MermaidBlock from "./components/MermaidBlock";
import "katex/dist/katex.min.css";
import styles from "./index.module.css";
import InlineCode from "./components/InlineCode";
import NormalCode from "./components/NormalCode";

import classNames from "classnames";
import GrayContainer, {
  LanguageLabel,
  CopyButton,
} from "./components/GrayContainer";

const CustomCodeBlock = ({ inline, className, children }: any) => {
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
      remarkPlugins={[remarkGfm, remarkRehype, remarkMath]} // Markdown 解析阶段, 处理原始 Markdown 文本，转换成 AST（抽象语法树）
      className={classNames(styles["markdown-body"], className)}
    >
      {children}
    </ReactMarkdown>
  );
};

export default memo(MarkdownContainer);
