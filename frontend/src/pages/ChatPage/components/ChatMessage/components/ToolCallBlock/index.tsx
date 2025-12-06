import { EventType, useEmitterWithCondition } from "@/events";
import { ToolCallMessage } from "@/interfaces";
import { isCallingTool } from "@/utils";
import { ToolOutlined } from "@ant-design/icons";
import { Think, ThoughtChain } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { isEmpty } from "lodash-es";
import React, { useState } from "react";
import TitleWithDuration from "../TitleWithDuration";
import { useTimelineMessages } from "./hooks";
import styles from "./index.module.css";
import ToolCallItemContent from "./ToolCallItemContent";
import ToolCallItemTitle from "./ToolCallItemTitle";

type Props = {
  isCallingTools: boolean;
  isStreaming: boolean;
  toolCallsDuration?: number;
  toolCalls: ToolCallMessage[] | undefined;
};

const ToolCallBlock = ({
  isCallingTools,
  isStreaming,
  toolCallsDuration,
  toolCalls,
}: Props) => {
  const timelineMessages = useTimelineMessages(toolCalls);
  const [expanded, setExpanded] = useState<boolean>(isStreaming ? true : false);
  const [expandedToolCallKeys, setExpandedToolCallKeys] = useState<string[]>(
    []
  );

  const handleExpandChange = useMemoizedFn((expand: boolean) => {
    setExpanded(expand);
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
      styles={{
        content: {
          borderColor: "transparent",
        },
      }}
      title={
        <TitleWithDuration
          titles={{
            doing: "工具调用中",
            done: "已完成工具调用",
          }}
          isDoing={isCallingTools}
          duration={toolCallsDuration}
        />
      }
    >
      <ThoughtChain
        classNames={{
          item: styles["thought-chain-item"],
        }}
        className="gap-2"
        expandedKeys={expandedToolCallKeys}
        onExpand={setExpandedToolCallKeys}
        items={timelineMessages.map((message, index) => ({
          key: message.key,
          status: message.status,
          collapsible: true,
          blink: isCallingTool(message.status),
          title: <ToolCallItemTitle index={index} message={message} />,
          content: <ToolCallItemContent message={message} />,
        }))}
      />
    </Think>
  );
};

export default React.memo(ToolCallBlock);
