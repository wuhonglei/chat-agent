import { ChatMessage as ChatMessageType } from "@/types";
import React from "react";
import AssistantMessage from "./components/AssistantMessage";
import UserMessage from "./components/UserMessage";
import { useMemoizedFn } from "ahooks";

interface ChatMessageItemProps {
  index: number;
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  onSourceClick: (index: number, message: ChatMessageType) => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  index,
  message,
  isStreaming,
  isLoading,
  isReasoning,
  onSourceClick,
}) => {
  const isUser = message.role === "user";
  const handleSourceClick = useMemoizedFn(() => {
    onSourceClick(index, message);
  });

  return isUser ? (
    <UserMessage message={message} />
  ) : (
    <AssistantMessage
      message={message}
      isLoading={isLoading}
      isStreaming={isStreaming}
      isReasoning={isReasoning}
      onSourceClick={handleSourceClick}
    />
  );
};

export default React.memo(ChatMessageItem);
