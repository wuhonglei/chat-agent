import { ChatMessage as ChatMessageType } from "@/types";
import React from "react";
import AssistantMessage from "./components/AssistantMessage";
import UserMessage from "./components/UserMessage";

interface ChatMessageItemProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  onSourceClick: () => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  isStreaming,
  isLoading,
  isReasoning,
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
      isReasoning={isReasoning}
      onSourceClick={onSourceClick}
    />
  );
};

export default React.memo(ChatMessageItem);
