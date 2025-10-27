import { ToolCallStatus } from "@/constants";

export interface ToolCall {
  id: string;
  type: "function_call";
  function: {
    arguments: string;
    name: string;
  };
}

export interface AssistantToolCallMessage {
  role: "assistant";
  status: "start" | "continue" | "done";
  content: string;
  toolCall: ToolCall;
  toolCallId: string;
}

export interface ToolCallResultMessage {
  role: "tool";
  status: "continue" | "error";
  toolCallId: string;
  duration: number;
  toolCall: ToolCall;
  content: string | Record<string, any>;
}

export type ToolCallMessage = AssistantToolCallMessage | ToolCallResultMessage;

export type TimelineMessage =
  | {
      key: string;
      status: ToolCallStatus.AllFinished;
      content: string;
    }
  | {
      key: string;
      status: ToolCallStatus.CallingTool;
      toolCallId: string;
      toolCall: ToolCall;
      content: string;
    }
  | {
      key: string;
      toolCallId: string;
      toolCall: ToolCall;
      duration: number;
      content: string | Record<string, any>;
      status: ToolCallStatus.ToolResultSuccess | ToolCallStatus.ToolResultError;
    };
