import ReactIcon from "@/assets/svg/ReactIcon.svg?react";
import { EventType } from "@/events";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { ToolOutlined } from "@ant-design/icons";
import { Bubble } from "@ant-design/x";
import { useThrottle } from "ahooks";
import React from "react";
import AssistantOperation from "./AssistantOperation";
import ReasoningBlock from "./ReasoningBlock";
import ToolCallBlock from "./ToolCallBlock";

interface AssistantMessageProps {
  message: ChatMessageType;
  isStreaming: boolean;
  isLoading: boolean;
  isReasoning: boolean;
  isCallingMcpTools: boolean;
  isCallingComponentTools: boolean;
  onReSend: () => void;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  isReasoning,
  isStreaming,
  isLoading,
  isCallingMcpTools,
  isCallingComponentTools,
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
      classNames={{ body: "w-full", content: "w-full" }}
      content={displayContent}
      contentRender={displayContent => (
        <div className="flex flex-col gap-2">
          {/* 渲染 Mcp 工具调用 */}
          <ToolCallBlock
            titles={{
              doing: "工具调用中",
              done: "已完成工具调用",
            }}
            icon={<ToolOutlined />}
            isStreaming={isStreaming}
            toolCalls={message.toolCalls}
            isCallingTools={isCallingMcpTools}
            eventType={EventType.McpToolCallDone}
            toolCallsDuration={message.toolCallsDuration}
            tokenStats={message.tokenStats?.mcpTools}
          />
          {/* 渲染组件工具调用 */}
          <ToolCallBlock
            titles={{
              doing: "组件构造中",
              done: "已完成组件构造",
            }}
            icon={<ReactIcon width={16} height={16} fill="currentColor" />}
            isStreaming={isStreaming}
            toolCalls={message.componentToolCalls}
            isCallingTools={isCallingComponentTools}
            eventType={EventType.ComponentToolCallDone}
            tokenStats={message.tokenStats?.componentTools}
            toolCallsDuration={message.componentToolCallsDuration}
          />
          {/* 渲染思考内容 */}
          <ReasoningBlock
            isReasoning={isReasoning}
            reasoning={message.reasoning}
            isStreaming={isStreaming}
            reasoningDuration={message.reasoningDuration}
          />
          {/* 渲染模型返回的内容 */}
          <MarkdownContainer className="text-base w-full">
            {displayContent}
          </MarkdownContainer>
        </div>
      )}
      footer={
        isStreaming ? null : (
          <AssistantOperation
            message={message}
            onReSend={onReSend}
            tokenStats={message.tokenStats}
          />
        )
      }
    />
  );
};

export default React.memo(AssistantMessage);
