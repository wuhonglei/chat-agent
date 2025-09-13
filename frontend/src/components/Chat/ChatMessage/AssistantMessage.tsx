import laughingImgUrl from "@/assets/imgs/laughing.webp";
import { ChatMessage as ChatMessageType } from "@/types";
import { useDebounce } from "ahooks";
import { Spin } from "antd";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import SourceAbstract from "./SourceAbstract";
import styles from "./assistantMessage.module.css";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  isLoading?: boolean;
  onSourceClick: () => void;
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
  isLoading = false,
  onSourceClick,
}) => {
  const displayContent = useDebounce(message.content, {
    wait: isStreaming && message.content ? 20 : 0,
  });

  return (
    <div className="flex flex-col gap-3 mb-4">
      <img
        width={24}
        height={24}
        alt="assistant"
        src={laughingImgUrl}
        className="rounded-full"
      />
      {isLoading ? (
        <div className="flex justify-start items-center">
          <Spin size="small" />{" "}
          <span className="ml-2 text-gray-500">搜索中...</span>
        </div>
      ) : (
        <>
          <ReactMarkdown
            components={components}
            remarkPlugins={[remarkGfm]}
            className={styles["markdown-body"]}
          >
            {displayContent}
          </ReactMarkdown>
          {!isEmpty(message.sources) && (
            <SourceAbstract sources={message.sources} onClick={onSourceClick} />
          )}
        </>
      )}
    </div>
  );
};

export default AssistantMessage;
