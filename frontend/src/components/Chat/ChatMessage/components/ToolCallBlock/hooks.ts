import { useMemo } from "react";
import { keyBy, pick } from "lodash-es";
import { ToolCallMessage, TimelineMessage } from "@/interfaces";
import { ToolCallStatus } from "@/constants";

export function useTimelineMessages(
  toolCallMessages: ToolCallMessage[] | undefined
): TimelineMessage[] {
  return useMemo(() => {
    const filterMessages = (toolCallMessages || []).filter(message =>
      ["continue", "error", "done"].includes(message.status)
    );
    const assistantMessages =
      filterMessages.filter(message => message.role === "assistant") || [];
    const toolMessages =
      filterMessages.filter(message => message.role === "tool") || [];
    const toolMessageById = keyBy(toolMessages, "toolCallId");
    return assistantMessages.map(message => {
      const { status, toolCallId } = message;
      if (status === "done") {
        return {
          key: "done",
          status: ToolCallStatus.AllFinished,
          content: message.content,
        };
      }

      const toolMessage = toolMessageById[toolCallId];
      if (!toolMessage) {
        return {
          key: toolCallId,
          status: ToolCallStatus.CallingTool,
          ...pick(message, ["content", "toolCallId", "toolCall"]),
        };
      }

      return {
        key: toolCallId,
        status:
          toolMessage.status === "continue"
            ? ToolCallStatus.ToolResultSuccess
            : ToolCallStatus.ToolResultError,
        ...pick(toolMessage, ["content", "toolCallId", "toolCall", "duration"]),
      };
    });
  }, [toolCallMessages]);
}
