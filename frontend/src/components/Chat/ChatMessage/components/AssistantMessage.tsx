import { ChatMessage as ChatMessageType } from "@/interfaces";
import { useThrottle } from "ahooks";
import React from "react";
import ReasoningBlock from "./ReasoningBlock";
import MarkdownContainer from "@/components/Chat/MarkdownContainer";
import AssistantOperation from "./AssistantOperation";
import ToolCallBlock from "./ToolCallBlock";
import { Bubble } from "@ant-design/x";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
  onSourceClick: () => void;
  onReSend: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isReasoning,
  isStreaming,
  isLoading,
  isCallingTools,
  onSourceClick,
  onReSend,
}) => {
  const displayContent = useThrottle(message.content, {
    wait: 100,
  });

  return (
    <Bubble
      placement="start"
      variant="borderless"
      loading={isLoading}
      className="w-full mt-4"
      content={displayContent}
      messageRender={displayContent => (
        <div className="flex flex-col gap-2">
          <ToolCallBlock
            isStreaming={isStreaming}
            isCallingTools={isCallingTools}
            toolCalls={message.toolCalls}
          />
          {/* 渲染思考内容 */}
          <ReasoningBlock
            isReasoning={isReasoning}
            sources={message.sources}
            reasoning={message.reasoning}
            onSourceClick={onSourceClick}
            isStreaming={isStreaming}
          />
          {/* 渲染模型返回的内容 */}
          <MarkdownContainer
            className="text-base w-full"
            sources={message.sources}
          >
            {displayContent}
          </MarkdownContainer>
        </div>
      )}
      footer={
        isStreaming ? null : (
          <AssistantOperation
            message={message}
            onReSend={onReSend}
            onSourceClick={onSourceClick}
          />
        )
      }
    />
  );
};

export default React.memo(AssistantMessage);
