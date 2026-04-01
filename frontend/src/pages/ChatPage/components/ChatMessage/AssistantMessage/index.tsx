import { ChatMessage as ChatMessageType } from "@/interfaces";
import { Bubble } from "@ant-design/x";
import React from "react";
import AssistantOperation from "../components/AssistantOperation";
import ContentBlocksRender from "./ContentBlocksRender";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  onReSend: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({ message, isStreaming, isLoading, onReSend }) => {
  return (
    <Bubble
      content=""
      placement="start"
      variant="borderless"
      loading={isLoading}
      className="w-full mt-4"
      classNames={{ body: "w-full", content: "w-full" }}
      contentRender={() => <ContentBlocksRender contentBlocks={message.contentBlocks} isStreaming={isStreaming} />}
      footer={isStreaming ? null : <AssistantOperation message={message} onReSend={onReSend} />}
    />
  );
};

export default React.memo(AssistantMessage);
