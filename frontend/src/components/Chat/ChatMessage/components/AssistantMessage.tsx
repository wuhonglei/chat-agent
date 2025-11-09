import { ChatMessage as ChatMessageType } from "@/interfaces";
import { useThrottle } from "ahooks";
import { Spin } from "antd";
import React from "react";
import ReasoningBlock from "./ReasoningBlock";
import MarkdownContainer from "@/components/Chat/MarkdownContainer";
import AssistantOperation from "./AssistantOperation";
import ToolCallBlock from "./ToolCallBlock";

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
    <div className={"flex flex-col mt-4 items-start gap-2"}>
      {isLoading ? (
        <div className="flex justify-start items-center">
          <Spin size="small" />
          <span className="ml-2 text-gray-500">等待中...</span>
        </div>
      ) : (
        <>
          <ToolCallBlock
            defaultOpen={message.defaultOpen}
            isCallingTools={isCallingTools}
            toolCalls={message.toolCalls}
          />
          {/* 渲染思考内容 */}
          <ReasoningBlock
            isReasoning={isReasoning}
            sources={message.sources}
            reasoning={message.reasoning}
            onSourceClick={onSourceClick}
            defaultOpen={message.defaultOpen}
          />
          {/* 渲染模型返回的内容 */}
          <MarkdownContainer
            className="text-base w-full"
            sources={message.sources}
          >
            {displayContent}
          </MarkdownContainer>
          {/* 渲染操作按钮 */}
          <AssistantOperation
            message={message}
            onReSend={onReSend}
            isStreaming={isStreaming}
            onSourceClick={onSourceClick}
          />
        </>
      )}
    </div>
  );
};

export default React.memo(AssistantMessage);
