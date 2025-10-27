import React, { Fragment } from "react";
import { Collapse, Timeline } from "antd";
import { ToolCallMessage } from "@/interfaces";
import { isEmpty } from "lodash-es";
import AssistantToolCallBlock from "./AssistantToolCallBlock";
import ToolToolCallResultBlock from "./ToolToolCallResultBlock";
import styles from "./index.module.css";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
};

const ToolCallBlock = ({ isCallingTools, toolCallMessages }: Props) => {
  if (isEmpty(toolCallMessages)) {
    return null;
  }

  console.info("toolCallMessages", toolCallMessages);

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
            <div className="flex mt-2">
              <Timeline
                className="w-full"
                items={(toolCallMessages || [])
                  .filter(message =>
                    ["continue", "error", "done"].includes(message.status)
                  )
                  .map((message, index) => ({
                    key: index,
                    children: (
                      <Fragment key={message.toolCallId}>
                        {message.role === "assistant" && (
                          <AssistantToolCallBlock message={message} />
                        )}
                        {message.role === "tool" && (
                          <ToolToolCallResultBlock message={message} />
                        )}
                      </Fragment>
                    ),
                  }))}
              />
            </div>
          ),
        },
      ]}
    />
  );
};

export default React.memo(ToolCallBlock);
