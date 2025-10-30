import { useMemo } from "react";
import { ToolCallMessage, TimelineMessage } from "@/interfaces";
import { ToolCallStatus } from "@/constants";
import { isEmpty } from "lodash-es";

export function useTimelineMessages(
  toolCallMessages: ToolCallMessage[] | undefined
): TimelineMessage[] {
  return useMemo(() => {
    const messages: TimelineMessage[] = [];
    const toolCallStartIndex: Record<string, number> = {};
    for (const message of toolCallMessages || []) {
      const { status, content, role } = message;
      if (!role && status === "start") {
        continue;
      }
      // 如果工具调用结束，并且有内容，则添加结束消息
      if (!role && status === "done" && !isEmpty(messages)) {
        messages.push({
          key: "done",
          content: content || "",
          status: ToolCallStatus.AllFinished,
        });
        continue;
      }

      if (role !== "tool") {
        continue;
      }

      if (status === "start") {
        toolCallStartIndex[message.toolCallId] = messages.length;
        messages.push({
          key: message.toolCallId,
          content: content || "",
          toolCallId: message.toolCallId,
          toolCall: message.toolCall,
          status: ToolCallStatus.CallingTool,
        });
        continue;
      }

      if (status === "done") {
        const startIndex = toolCallStartIndex[message.toolCallId];
        if (startIndex !== undefined) {
          messages[startIndex] = {
            key: message.toolCallId,
            content: content || "",
            toolCallId: message.toolCallId,
            toolCall: message.toolCall,
            duration: message.duration,
            status: ToolCallStatus.ToolResultSuccess,
          };
        }
        continue;
      }

      if (status === "error") {
        const startIndex = toolCallStartIndex[message.toolCallId];
        if (startIndex !== undefined) {
          messages[startIndex] = {
            key: message.toolCallId,
            content: content || "",
            toolCallId: message.toolCallId,
            toolCall: message.toolCall,
            duration: message.duration,
            status: ToolCallStatus.ToolResultError,
          };
        }
        continue;
      }

      continue;
    }
    return messages;
  }, [toolCallMessages]);
}
