import { ChatMessage as ChatMessageType } from "@/interfaces";
import { PdfBlock } from "@/interfaces/contentBlock";
import { useMemoizedFn } from "ahooks";
import React from "react";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

interface ChatMessageItemProps {
  index: number;
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isLastMessage: boolean;
  onEditMessage: (index: number, content: string) => void;
  onDeleteMessage: (messageId: string) => void | Promise<void>;
  onReSend: (index: number, message: ChatMessageType) => void;
  onPreviewPdf: (block: PdfBlock) => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  index,
  message,
  isLastMessage,
  isStreaming,
  isLoading,
  onEditMessage,
  onDeleteMessage,
  onReSend,
  onPreviewPdf,
}) => {
  const isUser = message.role === "user";
  const handleEditMessage = useMemoizedFn((content: string) => {
    onEditMessage(index, content);
  });
  const handleReSend = useMemoizedFn(() => {
    onReSend(index, message);
  });
  const handleDeleteMessage = useMemoizedFn(() => {
    onDeleteMessage(message.id);
  });

  return isUser ? (
    <UserMessage
      message={message}
      onEditMessage={handleEditMessage}
      onDeleteMessage={handleDeleteMessage}
      isLastMessage={isLastMessage}
      onPreviewPdf={onPreviewPdf}
    />
  ) : (
    <AssistantMessage
      message={message}
      isLastMessage={isLastMessage}
      isLoading={isLoading}
      isStreaming={isStreaming}
      onReSend={handleReSend}
      onDeleteMessage={handleDeleteMessage}
    />
  );
};

export default React.memo(ChatMessageItem);
