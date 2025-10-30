import React, { useState } from "react";
import { Collapse, Timeline } from "antd";
import { ToolCallMessage } from "@/interfaces";
import { isEmpty } from "lodash-es";
import styles from "./index.module.css";
import { useTimelineMessages } from "./hooks";
import ToolCallItem from "./ToolCallItem";
import { timelineColorByStatus } from "@/constants";
import classNames from "classnames";
import { useMemoizedFn } from "ahooks";
import { EventType, useEmitter } from "@/events";

type Props = {
  isCallingTools: boolean;
  toolCallMessages: ToolCallMessage[] | undefined;
};
const contentKey = "content";

const ToolCallBlock = ({ isCallingTools, toolCallMessages }: Props) => {
  const timelineMessages = useTimelineMessages(toolCallMessages);
  const [activeKeys, setActiveKeys] = useState<string[]>([contentKey]);

  const handleCollapseChange = useMemoizedFn((key: string[]) => {
    setActiveKeys(key);
  });

  /**
   * 工具调用结束后，折叠工具调用内容
   */
  useEmitter(EventType.ToolCallDone, () => {
    setTimeout(() => {
      setActiveKeys([]);
    }, 500);
  });

  if (isEmpty(timelineMessages)) {
    return null;
  }

  return (
    <Collapse
      ghost
      className="w-full"
      collapsible="header"
      activeKey={activeKeys}
      expandIconPosition="end"
      onChange={handleCollapseChange}
      items={[
        {
          key: contentKey,
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
