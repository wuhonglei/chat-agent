import { ToolCallStatus } from "@/constants";
import { TimelineMessage, ToolCallMessage } from "@/interfaces";
import { useMemo } from "react";

export function useTimelineMessages(
  toolCalls: ToolCallMessage[] | undefined
): TimelineMessage[] {
  return useMemo(() => {
    const messages: TimelineMessage[] = [];
    const toolCallStartIndex: Record<string, number> = {};
    for (const message of toolCalls || []) {
      const { status, content, role } = message;
      if ((!role && ["start", "done"].includes(status)) || role !== "tool") {
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
  }, [toolCalls]);
}
