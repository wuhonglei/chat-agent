import { Collapse, Divider, Tag } from "antd";
import styles from "./css/ToolCallBlock.module.css";
import {
  AssistantToolCallMessage,
  ToolCallMessage,
  ToolCallResultMessage,
} from "@/interfaces";
import React from "react";
import { isEmpty } from "lodash-es";
import NormalCode from "../../MarkdownContainer/components/NormalCode";
import GrayContainer from "../../MarkdownContainer/components/GrayContainer";
import McpServerIcon from "@/assets/svg/mcpServerIcon.svg?react";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
};

function formatStringToJson(args: string) {
  try {
    return JSON.stringify(JSON.parse(args.trim()), null, 2);
  } catch {
    return args.trim();
  }
}

const AssistantToolCallBlock = ({
  message,
}: {
  message: AssistantToolCallMessage;
}) => {
  const { status, content, toolCall } = message;
  if (status === "done" || !toolCall || !toolCall.function) {
    return content ? <div className="text-gray-600">{content}</div> : null;
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
        <NormalCode language="js">
          {`// arguments is:\n${formatStringToJson(toolCall.function.arguments)}`}
        </NormalCode>
      </GrayContainer>
    </div>
  );
};

const ToolToolCallBlock = ({ message }: { message: ToolCallResultMessage }) => {
  const { status, content } = message;
  if (status === "error" || !content) {
    return content ? (
      <div className="text-gray-600">
        {typeof content === "string"
          ? content
          : JSON.stringify(content, null, 2)}
      </div>
    ) : null;
  }

  return (
    <div className="flex flex-col gap-1 items-start">
      <GrayContainer
        className="w-full"
        header={
          <div>
            <span>result is:</span>
          </div>
        }
      >
        <NormalCode language="js" style={{ maxHeight: 500 }}>
          {JSON.stringify(content, null, 2)}
        </NormalCode>
      </GrayContainer>
    </div>
  );
};

const ToolCallBlock = ({ isCallingTools, toolCallMessages }: Props) => {
  if (isEmpty(toolCallMessages)) {
    return null;
  }

  return (
    <Collapse
      ghost
      className="w-full"
      collapsible="header"
      expandIconPosition="end"
      defaultActiveKey={["content"]}
      items={[
        {
          key: "content",
          label: (
            <span className="text-gray-600">
              {isCallingTools ? "工具调用中" : "已完成工具调用"}
            </span>
          ),
          styles: {
            header: { padding: 0, justifyContent: "flex-start" },
            body: { padding: 0 },
          },
          classNames: { header: styles.header },
          children: (
            <div className="flex gap-1 w-full">
              <div className="flex flex-col py-1 w-4 items-center gap-1 pb-3">
                <McpServerIcon
                  width="20"
                  height="20"
                  className="text-blue-500"
                />
                <Divider
                  type="vertical"
                  style={{
                    flex: 1,
                    marginLeft: 0,
                    marginRight: 0,
                  }}
                />
              </div>
              <div className="flex-1">
                {(toolCallMessages || [])
                  .filter(message =>
                    ["continue", "error"].includes(message.status)
                  )
                  .map((message, index) => (
                    <div key={index} className="w-full">
                      {message.role === "assistant" && (
                        <AssistantToolCallBlock message={message} />
                      )}
                      {message.role === "tool" && (
                        <ToolToolCallBlock message={message} />
                      )}
                    </div>
                  ))}
              </div>
            </div>
          ),
        },
      ]}
    />
  );
};

export default React.memo(ToolCallBlock);
