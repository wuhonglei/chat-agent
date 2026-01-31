import { EventType, useEmitterWithCondition } from "@/events";
import { ToolCallMessage } from "@/interfaces";
import { ComponentToolsTokenStats, MCPToolsTokenStats } from "@/interfaces/token";
import { isCallingTool } from "@/utils";
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
  eventType: EventType;
  titles: {
    doing: string;
    done: string;
  };
  icon: React.ReactNode;
  tokenStats?: MCPToolsTokenStats | ComponentToolsTokenStats;
  toolCalls: ToolCallMessage[] | undefined;
};

const ToolCallBlock = ({
  isCallingTools,
  isStreaming,
  toolCallsDuration,
  eventType,
  titles,
  icon,
  tokenStats,
  toolCalls,
}: Props) => {
  const timelineMessages = useTimelineMessages(toolCalls);
  const [expanded, setExpanded] = useState<boolean>(isStreaming ? true : false);
  const [expandedToolCallKeys, setExpandedToolCallKeys] = useState<string[]>([]);

  const handleExpandChange = useMemoizedFn((expand: boolean) => {
    setExpanded(expand);
  });

  /**
   * 工具调用结束后，折叠工具调用内容
   */
  useEmitterWithCondition(
    eventType,
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
      icon={icon}
      expanded={expanded}
      blink={isCallingTools}
      onExpand={handleExpandChange}
      styles={{
        content: {
          borderColor: "transparent",
        },
      }}
      title={
        <TitleWithDuration
          titles={titles}
          isDoing={isCallingTools}
          duration={toolCallsDuration}
          tokenStats={tokenStats}
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
