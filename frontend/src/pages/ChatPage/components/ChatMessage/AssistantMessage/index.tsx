import {
  ChatMessage as ChatMessageType,
  MessageFeedbackDetails,
  MessageFeedbackValue,
  MessageStatus,
} from "@/interfaces";
import { Bubble } from "@ant-design/x";
import React from "react";
import AssistantOperation from "../components/AssistantOperation";
import ContentBlocksRender from "./ContentBlocksRender";
import { useAssistantCanDelete, useIterationCheckpointActions } from "./hooks";
import IterationCheckpointActions from "./ContentBlocksRender/IterationCheckpointActions";

interface AssistantMessageProps {
  message: ChatMessageType;
  isLastMessage: boolean;
  isStreaming: boolean;
  isLoading: boolean;
  onReSend: () => void;
  onDeleteMessage: () => void | Promise<void>;
  onUpdateMessageFeedback: (value: MessageFeedbackValue, details?: MessageFeedbackDetails) => Promise<void>;
  onContinueTask?: () => void;
  onSummarizeTask?: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isLastMessage,
  isStreaming,
  isLoading,
  onReSend,
  onDeleteMessage,
  onUpdateMessageFeedback,
  onContinueTask,
  onSummarizeTask,
}) => {
  const canDelete = useAssistantCanDelete({
    isLastMessage,
    isStreaming,
    contentBlocks: message.contentBlocks,
  });
  const checkpointActions = useIterationCheckpointActions({
    checkpoint: message.messageMetadata?.iterationCheckpoint,
    isLastMessage,
    isStreaming,
    messageStatus: message.status,
    onContinue: onContinueTask,
    onSummarize: onSummarizeTask,
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
          {checkpointActions ? <IterationCheckpointActions {...checkpointActions} /> : null}
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
