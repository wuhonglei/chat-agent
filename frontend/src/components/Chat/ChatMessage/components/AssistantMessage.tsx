import { ChatMessage as ChatMessageType } from "@/types";
import { useThrottle } from "ahooks";
import { Spin } from "antd";
import React from "react";
import ReasoningBlock from "./ReasoningBlock";
import MarkdownContainer from "@/components/Chat/MarkdownContainer";
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
    <div className="flex flex-col gap-3 mb-4 items-start">
      {isLoading ? (
        <div className="flex justify-start items-center">
          <Spin size="small" />
          <span className="ml-2 text-gray-500">等待中...</span>
        </div>
      ) : (
        <>
          <ReasoningBlock
            isReasoning={isReasoning}
            sources={message.sources}
            reasoning={message.reasoning}
            onSourceClick={onSourceClick}
          />
          <MarkdownContainer
            className="text-base w-full"
            sources={message.sources}
          >
            {displayContent}
          </MarkdownContainer>
          {!isStreaming && (
            <SourceAbstract
              mode="postSource"
              sources={message.sources}
              onClick={onSourceClick}
            />
          )}
        </>
      )}
    </div>
  );
};

export default React.memo(AssistantMessage);
