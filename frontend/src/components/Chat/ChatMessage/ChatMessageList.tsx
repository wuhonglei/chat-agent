import { ChatMessage as ChatMessageType } from "@/interfaces";
import React, { useRef } from "react";
import ChatMessageItem from "./ChatMessageItem";
import { isEmpty } from "lodash-es";
import { Empty } from "antd";
import classNames from "classnames";
import { useAppSelector } from "@/store/hooks";

interface ChatMessageListProps {
  isLoading?: boolean;
  isStreaming?: boolean;
  isReasoning?: boolean;
  className?: string;
  onEditMessage: (index: number, content: string) => void;
  onReSend: (index: number, message: ChatMessageType) => void;
  onSourceClick: (index: number, message: ChatMessageType) => void;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  isLoading = false,
  isStreaming = false,
  isReasoning = false,
  className,
  onSourceClick,
  onEditMessage,
  onReSend,
}) => {
  const { messages } = useAppSelector(state => state.chat);
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
    <div className={classNames("flex-1 overflow-y-auto px-2 pb-4", className)}>
      {messages.map((message, index) => (
        <ChatMessageItem
          key={index}
          index={index}
          message={message}
          onReSend={onReSend}
          onSourceClick={onSourceClick}
          onEditMessage={onEditMessage}
          isLoading={isLoading && index === messages.length - 1}
          isStreaming={isStreaming && index === messages.length - 1}
          isReasoning={isReasoning && index === messages.length - 1}
        />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default React.memo(ChatMessageList);
