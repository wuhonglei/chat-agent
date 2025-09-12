import React, { useEffect, useState } from "react";
import { Avatar, Card } from "antd";
import { UserOutlined, RobotOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import dayjs from "dayjs";
import { ChatMessage as ChatMessageType } from "../../types";

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  isStreaming = false,
}) => {
  const [displayContent, setDisplayContent] = useState("");
  const isUser = message.role === "user";

  // Typing effect
  useEffect(() => {
    if (!isUser && isStreaming && message.content) {
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
  }, [message.content, isStreaming, isUser]);

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
    <div className={`flex gap-3 mb-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <Avatar
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        className={`${isUser ? "bg-blue-500" : "bg-green-500"}`}
      />
      <Card
        className={`flex-1 max-w-[70%] ${
          isUser ? "bg-blue-50" : "bg-gray-50"
        } animate-slide-up`}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <div className="prose prose-sm max-w-none">
          {isUser ? (
            <p className="mb-0">{displayContent}</p>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={components}
              className="markdown-body"
            >
              {displayContent}
            </ReactMarkdown>
          )}
        </div>
        <div className="text-xs text-gray-400 mt-2">
          {dayjs(message.timestamp).format("HH:mm:ss")}
        </div>
      </Card>
    </div>
  );
};

export default ChatMessage;
