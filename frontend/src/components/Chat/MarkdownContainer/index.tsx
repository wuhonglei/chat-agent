import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeExternalLinks from "rehype-external-links";
import remarkMath from "remark-math";
import MermaidBlock from "./components/MermaidBlock";
import classNames from "classnames";
import "katex/dist/katex.min.css";
import styles from "./index.module.css";
import InlineCode from "./components/InlineCode";
import NormalCode from "./components/NormalCode";

const CustomCodeBlock = ({ inline, className, children }: any) => {
  const match = /language-(\w+)/.exec(className || "");
  const code = String(children).replace(/\n$/, "");
  const language = match ? match[1] : "";

  // 处理 Mermaid 代码块
  if (!inline && match && match[1] === "mermaid") {
    return <MermaidBlock code={code} />;
  }

  if (inline || !language) {
    return (
      <InlineCode
        className={classNames(
          className,
          "bg-gray-100 px-1 py-0.5 text-sm rounded"
        )}
      >
        {children}
      </InlineCode>
    );
  }

  return <NormalCode language={language}>{code}</NormalCode>;
};

type Props = {
  children: string | undefined;
  className?: string;
};

export default function MarkdownContainer({ children, className }: Props) {
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
      remarkPlugins={[remarkGfm, remarkMath]} // Markdown 解析阶段, 处理原始 Markdown 文本，转换成 AST（抽象语法树）
      className={classNames(styles["markdown-body"], className)}
    >
      {children}
    </ReactMarkdown>
  );
}
