import { ToolCallStatus } from "@/constants";
import {
  TimelineMessage,
  ToolCallEndItemMessage,
  ToolCallMessage,
  ToolCallStartItemMessage,
} from "@/interfaces";
import { useMemo } from "react";

export function useTimelineMessages(
  toolCalls: ToolCallMessage[] | undefined
): TimelineMessage[] {
  return useMemo(() => {
    const messages: TimelineMessage[] = [];
    const toolCallStartIndex: Record<string, number> = {};
    for (const message of toolCalls || []) {
      const { role } = message;
      if (!role && ["start", "done"].includes(message.status)) {
        continue;
      }

      if (role === "assistant") {
        const { toolCalls } = message as ToolCallStartItemMessage;
        for (const toolCall of toolCalls) {
          toolCallStartIndex[toolCall.id] = messages.length;
          messages.push({
            key: toolCall.id,
            toolCallId: toolCall.id,
            toolCall: toolCall,
            content: message.content,
            status: ToolCallStatus.CallingTool,
            reasoningContent: message.reasoningContent,
          });
        }
        continue;
      }

      if (role === "tool") {
        const { toolCallId, duration, content, isError } =
          message as ToolCallEndItemMessage;
        const startIndex = toolCallStartIndex[toolCallId];
        if (startIndex !== undefined) {
          messages[startIndex] = {
            key: toolCallId,
            content: content || "",
            duration: duration,
            toolCallId: toolCallId,
            toolCall: messages[startIndex].toolCall,
            status: isError
              ? ToolCallStatus.ToolResultError
              : ToolCallStatus.ToolResultSuccess,
            reasoningContent: messages[startIndex].reasoningContent,
          };
        }
        continue;
      }
    }

    return messages;
  }, [toolCalls]);
}
