import { ChatMessage as ChatMessageType } from "@/interfaces";
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
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isLastMessage,
  isStreaming,
  isLoading,
  onReSend,
  onDeleteMessage,
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
      contentRender={() => <ContentBlocksRender contentBlocks={message.contentBlocks} isStreaming={isStreaming} />}
      footer={
        isStreaming ? null : (
          <AssistantOperation message={message} onReSend={onReSend} onDelete={onDeleteMessage} showDelete={canDelete} />
        )
      }
    />
  );
};

export default React.memo(AssistantMessage);
