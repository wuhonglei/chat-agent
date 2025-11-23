import { ChatMessage as ChatMessageType } from "@/interfaces";
import { useMemoizedFn } from "ahooks";
import React from "react";
import AssistantMessage from "./components/AssistantMessage";
import UserMessage from "./components/UserMessage";

interface ChatMessageItemProps {
  index: number;
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
  onSourceClick: (index: number, message: ChatMessageType) => void;
  onEditMessage: (index: number, content: string) => void;
  onReSend: (index: number, message: ChatMessageType) => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  index,
  message,
  isStreaming,
  isLoading,
  isReasoning,
  isCallingTools,
  onSourceClick,
  onEditMessage,
  onReSend,
}) => {
  const isUser = message.role === "user";
  const handleSourceClick = useMemoizedFn(() => {
    onSourceClick(index, message);
  });
  const handleEditMessage = useMemoizedFn((content: string) => {
    onEditMessage(index, content);
  });
  const handleReSend = useMemoizedFn(() => {
    onReSend(index, message);
  });

  return isUser ? (
    <UserMessage message={message} onEditMessage={handleEditMessage} />
  ) : (
    <AssistantMessage
      message={message}
      isLoading={isLoading}
      isStreaming={isStreaming}
      isReasoning={isReasoning}
      onReSend={handleReSend}
      isCallingTools={isCallingTools}
      onSourceClick={handleSourceClick}
    />
  );
};

export default React.memo(ChatMessageItem);
