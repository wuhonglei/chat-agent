import laughingImgUrl from "@/assets/imgs/laughing.webp";
import { ChatMessage as ChatMessageType } from "@/types";
import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import styles from "./assistantMessage.module.css";
interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isStreaming = false,
}) => {
  const [displayContent, setDisplayContent] = useState("");

  // Typing effect
  useEffect(() => {
    if (isStreaming && message.content) {
      let index = 0;
      const timer = setInterval(() => {
        if (index <= message.content.length) {
          setDisplayContent(message.content.slice(0, index));
          index++;
        } else {
          clearInterval(timer);
        }
      }, 20);
      return () => clearInterval(timer);
    } else {
      setDisplayContent(message.content);
    }
  }, [message.content, isStreaming]);

  const components = {
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || "");
      return !inline && match ? (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={match[1]}
          PreTag="div"
          {...props}
        >
          {String(children).replace(/\n$/, "")}
        </SyntaxHighlighter>
      ) : (
        <code
          className={`${className} bg-gray-100 px-1 py-0.5 rounded`}
          {...props}
        >
          {children}
        </code>
      );
    },
  };

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
        remarkPlugins={[remarkGfm]}
        components={components}
        className={styles["markdown-body"]}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  );
};

export default AssistantMessage;
