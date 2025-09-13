import laughingImgUrl from "@/assets/imgs/laughing.webp";
import { ChatMessage as ChatMessageType } from "@/types";
import { useDebounce } from "ahooks";
import classNames from "classnames";
import React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import styles from "./assistantMessage.module.css";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

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

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isStreaming = false,
}) => {
  const displayContent = useDebounce(message.content, {
    wait: isStreaming && message.content ? 20 : 0,
  });

  return (
    <div className="flex flex-col gap-3 mb-4">
      <img
        src={laughingImgUrl}
        alt="assistant"
        width={24}
        height={24}
        className="rounded-full"
      />
      <ReactMarkdown
        components={components}
        remarkPlugins={[remarkGfm]}
        className={styles["markdown-body"]}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  );
};

export default AssistantMessage;
