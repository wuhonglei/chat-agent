import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import classNames from "classnames";
import styles from "./css/MarkdownContainer.module.css";

const components = {
  code({ node, inline, className, children, ...props }: any) {
    const match = /language-(\w+)/.exec(className || "");
    return !inline && match ? (
      <SyntaxHighlighter style={vs} language={match[1]} {...props}>
        {String(children).replace(/\n$/, "")}
      </SyntaxHighlighter>
    ) : (
      <code
        className={classNames(className, "bg-gray-100 px-1 py-0.5 rounded")}
        {...props}
      >
        {children}
      </code>
    );
  },
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
      components={components}
      remarkPlugins={[remarkGfm]}
      className={classNames(styles["markdown-body"], className)}
    >
      {children}
    </ReactMarkdown>
  );
}
