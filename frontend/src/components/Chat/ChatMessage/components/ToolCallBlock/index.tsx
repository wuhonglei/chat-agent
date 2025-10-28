import React from "react";
import { Collapse, Timeline } from "antd";
import { ToolCallMessage } from "@/interfaces";
import { isEmpty } from "lodash-es";
import styles from "./index.module.css";
import { useTimelineMessages } from "./hooks";
import ToolCallItem from "./ToolCallItem";
import { timelineColorByStatus } from "@/constants";
import classNames from "classnames";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
};

const ToolCallBlock = ({ isCallingTools, toolCallMessages }: Props) => {
  const timelineMessages = useTimelineMessages(toolCallMessages);
  if (isEmpty(timelineMessages)) {
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
            <div className="flex mt-2 pl-1">
              <Timeline
                pending={isCallingTools ? "waiting for tool result ..." : false}
                className={classNames("w-full", styles["timeline-container"])}
                items={timelineMessages.map(message => ({
                  key: message.key,
                  color: timelineColorByStatus[message.status],
                  children: <ToolCallItem message={message} />,
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
