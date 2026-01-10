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
  status: "done";
  content: string;
  duration?: number;
}

// 工具调用结果消息
export interface ToolCallStartItemMessage {
  role: "assistant";
  content: string;
  status: undefined;
  reasoningContent: string;
  toolCalls: ToolCall[];
}

export interface ToolCallEndItemMessage {
  role: "tool";
  isError: boolean;
  content: string;
  toolCallId: string;
  duration: number;
  tokenCount?: number;
}

export type ToolCallMessage =
  | ToolCallProcessMessage
  | ToolCallStartItemMessage
  | ToolCallEndItemMessage;

export type TimelineMessage =
  | {
      key: string;
      content: string;
      toolCallId: string;
      toolCall: ToolCall;
      reasoningContent: string;
      status: ToolCallStatus.CallingTool;
    }
  | {
      key: string;
      toolCallId: string;
      toolCall: ToolCall;
      duration: number;
      reasoningContent: string;
      tokenCount?: number;
      content: string | Record<string, unknown>;
      status: ToolCallStatus.ToolResultSuccess | ToolCallStatus.ToolResultError;
    };
