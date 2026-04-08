import { useChatState } from "@/hooks";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import classNames from "classnames";
import React, { useRef } from "react";
import SimpleBar from "simplebar-react";
import ChatMessageItem from "./ChatMessageItem";
import AutoScroll from "./components/AutoScroll";
import FloatButtonBottom from "./components/FloatButtonBottom";

interface ChatMessageListProps {
  conversationId: string;
  isLoading?: boolean;
  isStreaming?: boolean;
  className?: string;
  onEditMessage: (index: number, content: string) => void;
  onReSend: (index: number, message: ChatMessageType) => void;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  conversationId,
  isLoading = false,
  isStreaming = false,
  className,
  onEditMessage,
  onReSend,
}) => {
  const { messages } = useChatState(conversationId);
  const containerRef = useRef<HTMLDivElement>(null);
  return (
    <SimpleBar
      scrollableNodeProps={{
        ref: containerRef,
        className: "outline-none",
      }}
      className={classNames("flex-1 h-0 px-2 pb-4 relative ", className)}
    >
      {messages.map((message, index) => (
        <ChatMessageItem
          index={index}
          key={message.id}
          message={message}
          onReSend={onReSend}
          onEditMessage={onEditMessage}
          isLoading={isLoading && index === messages.length - 1}
          isStreaming={isStreaming && index === messages.length - 1}
        />
      ))}
      <AutoScroll messages={messages} isStreaming={isStreaming} containerRef={containerRef} />
      <FloatButtonBottom visibilityHeight={200} containerRef={containerRef} />
    </SimpleBar>
  );
};

export default React.memo(ChatMessageList);
