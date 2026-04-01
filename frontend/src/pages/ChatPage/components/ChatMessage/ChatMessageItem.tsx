import { ChatMessage as ChatMessageType } from "@/interfaces";
import { useMemoizedFn } from "ahooks";
import React from "react";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

interface ChatMessageItemProps {
  index: number;
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  onEditMessage: (index: number, content: string) => void;
  onReSend: (index: number, message: ChatMessageType) => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  index,
  message,
  isStreaming,
  isLoading,
  onEditMessage,
  onReSend,
}) => {
  const isUser = message.role === "user";
  const handleEditMessage = useMemoizedFn((content: string) => {
    onEditMessage(index, content);
  });
  const handleReSend = useMemoizedFn(() => {
    onReSend(index, message);
  });

  return isUser ? (
    <UserMessage message={message} onEditMessage={handleEditMessage} />
  ) : (
    <AssistantMessage message={message} isLoading={isLoading} isStreaming={isStreaming} onReSend={handleReSend} />
  );
};

export default React.memo(ChatMessageItem);
