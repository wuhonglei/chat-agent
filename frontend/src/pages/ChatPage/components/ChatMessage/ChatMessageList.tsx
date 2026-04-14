import { useChatState } from "@/hooks";
import { ChatMessage as ChatMessageType, MessageFeedbackValue } from "@/interfaces";
import { PdfBlock } from "@/interfaces/contentBlock";
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
  onDeleteMessage: (messageId: string) => void | Promise<void>;
  onUpdateMessageFeedback: (messageId: string, value: MessageFeedbackValue) => Promise<void>;
  onReSend: (index: number, message: ChatMessageType) => void;
  onPreviewPdf: (block: PdfBlock) => void;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  conversationId,
  isLoading = false,
  isStreaming = false,
  className,
  onEditMessage,
  onDeleteMessage,
  onUpdateMessageFeedback,
  onReSend,
  onPreviewPdf,
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
          onPreviewPdf={onPreviewPdf}
          onEditMessage={onEditMessage}
          onDeleteMessage={onDeleteMessage}
          onUpdateMessageFeedback={onUpdateMessageFeedback}
          isLastMessage={index === messages.length - 1}
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
