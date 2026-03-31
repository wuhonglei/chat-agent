import { ChatMessage as ChatMessageType } from "@/interfaces";
import { Bubble } from "@ant-design/x";
import React from "react";
import AssistantOperation from "./AssistantOperation";
import ContentBlocksRenderer from "./ContentBlocksRenderer";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  onReSend: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({ message, isStreaming, isLoading, onReSend }) => {
  return (
    <Bubble
      placement="start"
      variant="borderless"
      loading={isLoading}
      className="w-full mt-4"
      classNames={{ body: "w-full", content: "w-full" }}
      content=""
      contentRender={() => <ContentBlocksRenderer contentBlocks={message.contentBlocks} />}
      footer={isStreaming ? null : <AssistantOperation message={message} onReSend={onReSend} />}
    />
  );
};

export default React.memo(AssistantMessage);
