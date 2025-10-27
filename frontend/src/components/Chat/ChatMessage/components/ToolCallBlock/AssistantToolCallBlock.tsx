import React from "react";
import { AssistantToolCallMessage } from "@/interfaces";
import { Tag } from "antd";
import NormalCode from "@/components/Chat/MarkdownContainer/components/NormalCode";
import GrayContainer from "@/components/Chat/MarkdownContainer/components/GrayContainer";

function stringifyArgs(args: string): string {
  if (!args) {
    return "";
  }

  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

interface AssistantToolCallBlockProps {
  message: AssistantToolCallMessage;
}

const AssistantToolCallBlock: React.FC<AssistantToolCallBlockProps> = ({
  message,
}) => {
  const { status, content, toolCall } = message;
  if (status === "done" || !toolCall || !toolCall.function) {
    return content ? <div className="w-full">{content}</div> : null;
  }

  // 函数调用中
  return (
    <div className="w-full">
      <GrayContainer
        className="flex flex-col gap-1 items-start w-full"
        header={
          <div className="flex items-center gap-2">
            <span>calling tool</span>
            <Tag bordered={false} style={{ marginRight: 0 }}>
              {toolCall.function.name}
            </Tag>
          </div>
        }
      >
        <NormalCode language="json">
          {stringifyArgs(toolCall.function.arguments)}
        </NormalCode>
      </GrayContainer>
    </div>
  );
};

export default React.memo(AssistantToolCallBlock);
