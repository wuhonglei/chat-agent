import { ChatMessage as ChatMessageType } from "@/types";
import React from "react";
import AssistantMessage from "./components/AssistantMessage";
import UserMessage from "./components/UserMessage";

interface ChatMessageItemProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  isLoading?: boolean;
  onSourceClick: () => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  isStreaming = false,
  isLoading = false,
  onSourceClick,
}) => {
  const isUser = message.role === "user";

  return isUser ? (
    <UserMessage message={message} />
  ) : (
    <AssistantMessage
      message={message}
      isStreaming={isStreaming}
      isLoading={isLoading}
      onSourceClick={onSourceClick}
    />
  );
};

export default ChatMessageItem;
