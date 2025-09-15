import { ChatMessage as ChatMessageType } from "@/types";
import React, { useRef } from "react";
import ChatMessageItem from "./ChatMessageItem";
import { isEmpty } from "lodash-es";
import { Empty } from "antd";
import classNames from "classnames";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  isLoading?: boolean;
  isStreaming?: boolean;
  className?: string;
  onSourceClick: (index: number, message: ChatMessageType) => void;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  isLoading = false,
  isStreaming = false,
  className,
  onSourceClick,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  if (isEmpty(messages)) {
    return (
      <Empty
        description="开始提问吧"
        className={classNames(
          "flex-1 flex flex-col items-center justify-center",
          className
        )}
      />
    );
  }

  return (
    <div className={classNames("flex-1 overflow-y-auto px-2", className)}>
      {messages.map((message, index) => (
        <ChatMessageItem
          key={index}
          message={message}
          isLoading={isLoading && index === messages.length - 1}
          isStreaming={isStreaming && index === messages.length - 1}
          onSourceClick={() => onSourceClick(index, message)}
        />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatMessageList;
