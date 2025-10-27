import { Collapse, Divider, Tag } from "antd";
import styles from "./css/ToolCallBlock.module.css";
import {
  AssistantToolCallMessage,
  ToolCallMessage,
  ToolCallResultMessage,
} from "@/interfaces";
import React, { Fragment, useMemo } from "react";
import { isEmpty, isPlainObject } from "lodash-es";
import NormalCode from "@/components/Chat/MarkdownContainer/components/NormalCode";
import GrayContainer from "@/components/Chat/MarkdownContainer/components/GrayContainer";
import McpServerIcon from "@/assets/svg/mcpServerIcon.svg?react";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
};

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

function stringifyContentWithLanguage<T extends string | Record<string, any>>(
  content: T | undefined
): [string, string] {
  if (!content) {
    return ["", ""];
  }

  if (isPlainObject(content)) {
    return [JSON.stringify(content, null, 2), "json"];
  }

  try {
    const str = JSON.stringify(JSON.parse(content as string), null, 2);
    return [str, "json"];
  } catch {
    return [content as string, "markdown"];
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
        <NormalCode language="json">
          {stringifyArgs(toolCall.function.arguments)}
        </NormalCode>
      </GrayContainer>
    </div>
  );
};

const ToolToolCallResultBlock = ({
  message,
}: {
  message: ToolCallResultMessage;
}) => {
  const { content } = message;
  const [contentStr, language] = useMemo(
    () => stringifyContentWithLanguage(content),
    [content]
  );

  return (
    <div className="w-full">
      <GrayContainer
        className="w-full"
        header={
          <div>
            <span>result is:</span>
          </div>
        }
      >
        <NormalCode language={language} style={{ maxHeight: 500 }}>
          {contentStr}
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
              <div className="flex-1 overflow-hidden">
                {(toolCallMessages || [])
                  .filter(message =>
                    ["continue", "error"].includes(message.status)
                  )
                  .map((message, index) => (
                    <Fragment key={index}>
                      {message.role === "assistant" && (
                        <AssistantToolCallBlock message={message} />
                      )}
                      {message.role === "tool" && (
                        <ToolToolCallResultBlock message={message} />
                      )}
                    </Fragment>
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
