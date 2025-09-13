import { ChatMessage as ChatMessageType } from "@/types";
import React from "react";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  isStreaming = false,
}) => {
  const isUser = message.role === "user";

  return isUser ? (
    <UserMessage message={message} />
  ) : (
    <AssistantMessage message={message} isStreaming={isStreaming} />
  );
};

export default ChatMessage;
