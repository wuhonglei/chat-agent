import { ChatMessage as ChatMessageType, MessageFeedbackValue, MessageStatus } from "@/interfaces";
import { Bubble } from "@ant-design/x";
import React from "react";
import AssistantOperation from "../components/AssistantOperation";
import ContentBlocksRender from "./ContentBlocksRender";
import { useAssistantCanDelete } from "./hooks";

interface AssistantMessageProps {
  message: ChatMessageType;
  isLastMessage: boolean;
  isStreaming: boolean;
  isLoading: boolean;
  onReSend: () => void;
  onDeleteMessage: () => void | Promise<void>;
  onUpdateMessageFeedback: (value: MessageFeedbackValue) => Promise<void>;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isLastMessage,
  isStreaming,
  isLoading,
  onReSend,
  onDeleteMessage,
  onUpdateMessageFeedback,
}) => {
  const canDelete = useAssistantCanDelete({
    isLastMessage,
    isStreaming,
    contentBlocks: message.contentBlocks,
  });

  return (
    <Bubble
      content=""
      placement="start"
      variant="borderless"
      loading={isLoading}
      className="w-full mt-4"
      classNames={{ body: "w-full", content: "w-full" }}
      contentRender={() => (
        <>
          <ContentBlocksRender contentBlocks={message.contentBlocks} isStreaming={isStreaming} />
          {message.status === MessageStatus.Stopped && <div className="text-gray-400 text-sm mt-2">Output Stopped</div>}
        </>
      )}
      footer={
        isStreaming ? null : (
          <AssistantOperation
            message={message}
            onReSend={onReSend}
            onDelete={onDeleteMessage}
            showDelete={canDelete}
            onFeedback={onUpdateMessageFeedback}
          />
        )
      }
    />
  );
};

export default React.memo(AssistantMessage);
