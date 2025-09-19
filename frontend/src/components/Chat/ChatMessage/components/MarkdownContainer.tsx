import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import classNames from "classnames";
import styles from "./css/MarkdownContainer.module.css";

const customStyle = {
  backgroundColor: "#F8F9FA",
  border: "none",
  borderRadius: "12px",
  marginTop: 0,
};

const components = {
  code({ node, inline, className, children, ...props }: any) {
    const match = /language-(\w+)/.exec(className || "");

    console.info("vs", vs);
    console.info("node", node);

    return !inline && match ? (
      <SyntaxHighlighter
        style={vs}
        customStyle={customStyle}
        language={match[1]}
        {...props}
      >
        {String(children).replace(/\n$/, "")}
      </SyntaxHighlighter>
    ) : (
      <code
        className={classNames(
          className,
          "bg-gray-100 px-1 py-0.5 text-sm rounded"
        )}
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
