import { ChatMessage as ChatMessageType } from "@/interfaces";
import React, { useRef } from "react";
import ChatMessageItem from "./ChatMessageItem";
import classNames from "classnames";
import AutoScroll from "./components/AutoScroll";
import FloatButtonBottom from "./components/FloatButtonBottom";
import { useChatState } from "@/hooks";

interface ChatMessageListProps {
  conversationId: string;
  isLoading?: boolean;
  isStreaming?: boolean;
  isReasoning?: boolean;
  isCallingTools?: boolean;
  className?: string;
  onEditMessage: (index: number, content: string) => void;
  onReSend: (index: number, message: ChatMessageType) => void;
  onSourceClick: (index: number, message: ChatMessageType) => void;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  conversationId,
  isLoading = false,
  isStreaming = false,
  isReasoning = false,
  isCallingTools = false,
  className,
  onSourceClick,
  onEditMessage,
  onReSend,
}) => {
  const { messages } = useChatState(conversationId);
  const containerRef = useRef<HTMLDivElement>(null);
  return (
    <div
      ref={containerRef}
      className={classNames(
        "flex-1 overflow-y-auto px-2 pb-4 relative",
        className
      )}
    >
      {messages.map((message, index) => (
        <ChatMessageItem
          index={index}
          key={message.id}
          message={message}
          onReSend={onReSend}
          onSourceClick={onSourceClick}
          onEditMessage={onEditMessage}
          isLoading={isLoading && index === messages.length - 1}
          isStreaming={isStreaming && index === messages.length - 1}
          isReasoning={isReasoning && index === messages.length - 1}
          isCallingTools={isCallingTools && index === messages.length - 1}
        />
      ))}
      <AutoScroll
        messages={messages}
        isStreaming={isStreaming}
        containerRef={containerRef}
      />
      <FloatButtonBottom visibilityHeight={200} containerRef={containerRef} />
    </div>
  );
};

export default React.memo(ChatMessageList);
