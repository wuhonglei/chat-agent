import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import remarkMath from "remark-math";
import mermaid from "mermaid";
import classNames from "classnames";
import { useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import "katex/dist/katex.min.css";
import styles from "./index.module.css";

// 初始化 Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: "forest",
  securityLevel: "loose",
});

const customStyle = {
  backgroundColor: "#F8F9FA",
  border: "none",
  borderRadius: "12px",
  marginTop: 0,
};

const MermaidBlock = ({ code }: { code: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const idRef = useRef<string>(`mermaid-${uuidv4()}`);

  useEffect(() => {
    if (ref.current) {
      mermaid
        .render(idRef.current, code)
        .then(result => {
          if (ref.current) {
            console.info("result", result);
            ref.current.innerHTML = result.svg;
          }
        })
        .catch(error => {
          console.error("Mermaid rendering error:", error);
          if (ref.current) {
            ref.current.innerHTML = `<pre>${code}</pre>`;
          }
        });
    }
  }, [code]);

  return <div ref={ref} className="mermaid" />;
};

const CustomCodeBlock = ({ inline, className, children, ...rest }: any) => {
  const match = /language-(\w+)/.exec(className || "");
  const code = String(children).replace(/\n$/, "");

  // 处理 Mermaid 代码块
  if (!inline && match && match[1] === "mermaid") {
    return <MermaidBlock code={code} />;
  }

  if (inline || !match) {
    return (
      <code
        {...rest}
        className={classNames(
          className,
          "bg-gray-100 px-1 py-0.5 text-sm rounded"
        )}
      >
        {children}
      </code>
    );
  }

  return (
    <SyntaxHighlighter
      {...rest}
      style={vs}
      PreTag="div"
      children={code}
      language={match[1]}
      customStyle={customStyle}
    />
  );
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
      rehypePlugins={[rehypeRaw, rehypeKatex]} // HTML 生成阶段, 处理已转换的 HTML 树，在渲染前进行最终处理
      remarkPlugins={[remarkGfm, remarkMath]} // Markdown 解析阶段, 处理原始 Markdown 文本，转换成 AST（抽象语法树）
      className={classNames(styles["markdown-body"], className)}
    >
      {children}
    </ReactMarkdown>
  );
}
