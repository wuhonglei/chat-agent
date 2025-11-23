import { timelineColorByStatus } from "@/constants";
import { emitter, EventType, useEmitterWithCondition } from "@/events";
import { ToolCallMessage } from "@/interfaces";
import { useMemoizedFn } from "ahooks";
import { Collapse, Timeline } from "antd";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import React, { useState } from "react";
import { useTimelineMessages } from "./hooks";
import styles from "./index.module.css";
import ToolCallItem from "./ToolCallItem";

type Props = {
  isCallingTools: boolean;
  isStreaming: boolean;
  toolCalls: ToolCallMessage[] | undefined;
};
const contentKey = "content";

const ToolCallBlock = ({ isCallingTools, isStreaming, toolCalls }: Props) => {
  const timelineMessages = useTimelineMessages(toolCalls);
  const [activeKeys, setActiveKeys] = useState<string[]>(
    isStreaming ? [contentKey] : []
  );

  const handleCollapseChange = useMemoizedFn((keys: string[]) => {
    setActiveKeys(keys);
    emitter.emit(EventType.BlockCollapse, isEmpty(keys));
  });

  /**
   * 工具调用结束后，折叠工具调用内容
   */
  useEmitterWithCondition(
    EventType.ToolCallDone,
    () => {
      setTimeout(() => {
        setActiveKeys([]);
      }, 500);
    },
    isCallingTools
  );

  if (isEmpty(timelineMessages)) {
    return null;
  }

  return (
    <Collapse
      ghost
      className="w-full"
      collapsible="header"
      activeKey={activeKeys}
      expandIconPlacement="end"
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
                items={timelineMessages.map((message, index) => ({
                  key: message.key,
                  color: timelineColorByStatus[message.status],
                  children: <ToolCallItem message={message} index={index} />,
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
