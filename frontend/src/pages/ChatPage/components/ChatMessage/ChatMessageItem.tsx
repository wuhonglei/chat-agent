import { ChatMessage as ChatMessageType, MessageFeedbackDetails, MessageFeedbackValue } from "@/interfaces";
import type { PreviewableBlock } from "@/interfaces/contentBlock";
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
  onUpdateMessageFeedback: (
    messageId: string,
    value: MessageFeedbackValue,
    details?: MessageFeedbackDetails
  ) => Promise<void>;
  onReSend: (index: number, message: ChatMessageType) => void;
  onPreviewBlock: (block: PreviewableBlock) => void;
}

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  index,
  message,
  isLastMessage,
  isStreaming,
  isLoading,
  onEditMessage,
  onDeleteMessage,
  onUpdateMessageFeedback,
  onReSend,
  onPreviewBlock,
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
  const handleUpdateFeedback = useMemoizedFn((value: MessageFeedbackValue, details?: MessageFeedbackDetails) => {
    return onUpdateMessageFeedback(message.id, value, details);
  });

  return isUser ? (
    <UserMessage
      message={message}
      onEditMessage={handleEditMessage}
      onDeleteMessage={handleDeleteMessage}
      isLastMessage={isLastMessage}
      onPreviewBlock={onPreviewBlock}
    />
  ) : (
    <AssistantMessage
      message={message}
      isLastMessage={isLastMessage}
      isLoading={isLoading}
      isStreaming={isStreaming}
      onReSend={handleReSend}
      onDeleteMessage={handleDeleteMessage}
      onUpdateMessageFeedback={handleUpdateFeedback}
    />
  );
};

export default React.memo(ChatMessageItem);
