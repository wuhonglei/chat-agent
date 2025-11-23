import { ToolCallStatus } from "@/constants";

export interface ToolCall {
  id: string;
  type: "function_call";
  function: {
    arguments: string;
    name: string;
  };
}

// 工具调用流程的开始和结束消息
export interface ToolCallProcessMessage {
  role: undefined;
  status: "start" | "done";
  content: string;
}

// 工具调用结果消息
export interface ToolCallStartItemMessage {
  role: "tool";
  status: "start";
  duration: number;
  toolCall: ToolCall;
  toolCallId: string;
  content: string;
}

export interface ToolCallEndItemMessage {
  role: "tool";
  status: "done" | "error";
  duration: number;
  toolCall: ToolCall;
  toolCallId: string;
  content: string | Record<string, unknown>;
}

export type ToolCallMessage =
  | ToolCallProcessMessage
  | ToolCallStartItemMessage
  | ToolCallEndItemMessage;

export type TimelineMessage =
  | {
      key: "done";
      content: string;
      status: ToolCallStatus.AllFinished;
    }
  | {
      key: string;
      content: string;
      toolCallId: string;
      toolCall: ToolCall;
      status: ToolCallStatus.CallingTool;
    }
  | {
      key: string;
      toolCallId: string;
      toolCall: ToolCall;
      duration: number;
      content: string | Record<string, unknown>;
      status: ToolCallStatus.ToolResultSuccess | ToolCallStatus.ToolResultError;
    };
