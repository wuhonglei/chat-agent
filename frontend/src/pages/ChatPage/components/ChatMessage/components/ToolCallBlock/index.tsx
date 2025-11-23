import { emitter, EventType, useEmitterWithCondition } from "@/events";
import { ToolCallMessage } from "@/interfaces";
import { isCallingTool } from "@/utils";
import { ToolOutlined } from "@ant-design/icons";
import { Think, ThoughtChain } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { isEmpty } from "lodash-es";
import React, { useState } from "react";
import { useTimelineMessages } from "./hooks";
import styles from "./index.module.css";
import ToolCallItem from "./ToolCallItem";
import ToolCallTitle from "./ToolCallTitle";

type Props = {
  isCallingTools: boolean;
  isStreaming: boolean;
  toolCalls: ToolCallMessage[] | undefined;
};

const ToolCallBlock = ({ isCallingTools, isStreaming, toolCalls }: Props) => {
  const timelineMessages = useTimelineMessages(toolCalls);
  const [expanded, setExpanded] = useState<boolean>(isStreaming ? true : false);

  const handleExpandChange = useMemoizedFn((expand: boolean) => {
    setExpanded(expand);
    emitter.emit(EventType.BlockCollapse, expand);
  });

  /**
   * 工具调用结束后，折叠工具调用内容
   */
  useEmitterWithCondition(
    EventType.ToolCallDone,
    () => {
      setTimeout(() => {
        setExpanded(false);
      }, 500);
    },
    isCallingTools
  );

  if (isEmpty(timelineMessages)) {
    return null;
  }

  return (
    <Think
      expanded={expanded}
      blink={isCallingTools}
      icon={<ToolOutlined />}
      onExpand={handleExpandChange}
      title={isCallingTools ? "工具调用中" : "已完成工具调用"}
    >
      <ThoughtChain
        classNames={{
          item: styles["thought-chain-item"],
        }}
        className="gap-1"
        items={timelineMessages.map((message, index) => ({
          key: message.key,
          collapsible: true,
          status: message.status,
          blink: isCallingTool(message.status),
          title: <ToolCallTitle index={index} message={message} />,
          content: <ToolCallItem message={message} />,
        }))}
      />
    </Think>
  );
};

export default React.memo(ToolCallBlock);
