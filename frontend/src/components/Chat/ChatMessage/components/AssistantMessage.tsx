import { ChatMessage as ChatMessageType } from "@/types";
import { useThrottle } from "ahooks";
import { Spin } from "antd";
import React from "react";
import ReasoningBlock from "./ReasoningBlock";
import MarkdownContainer from "./MarkdownContainer";
import SourceAbstract from "./SourceAbstract";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  onSourceClick: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isReasoning,
  isStreaming,
  isLoading,
  onSourceClick,
}) => {
  const displayContent = useThrottle(message.content, {
    wait: 100,
  });

  return (
    <div className="flex flex-col gap-3 mb-4">
      {isLoading ? (
        <div className="flex justify-start items-center">
          <Spin size="small" />
          <span className="ml-2 text-gray-500">等待中...</span>
        </div>
      ) : (
        <>
          <ReasoningBlock
            isReasoning={isReasoning}
            reasoning={message.reasoning}
          />
          <MarkdownContainer className="text-base">
            {displayContent}
          </MarkdownContainer>
          <SourceAbstract sources={message.sources} onClick={onSourceClick} />
        </>
      )}
    </div>
  );
};

export default AssistantMessage;
