import { Collapse, Divider } from "antd";
import styles from "./css/ToolCallBlock.module.css";
import { ToolCallMessage } from "@/interfaces";
import React, { Fragment } from "react";
import { isEmpty } from "lodash-es";
import McpServerIcon from "@/assets/svg/mcpServerIcon.svg?react";
import AssistantToolCallBlock from "./AssistantToolCallBlock";
import ToolToolCallResultBlock from "./ToolToolCallResultBlock";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
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
