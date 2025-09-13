import { ChatMessage as ChatMessageType } from "@/types";
import React from "react";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  isLoading?: boolean;
  onSourceClick: () => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
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
      isLoading={isLoading}
      isStreaming={isStreaming}
      onSourceClick={onSourceClick}
    />
  );
};

export default ChatMessage;
