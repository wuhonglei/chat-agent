import { MCPToolsTokenStats } from "./token";

export enum ToolCallStatus {
  Start = "start",
  CallingTool = "loading",
  ToolResultSuccess = "success",
  ToolResultError = "error",
  AllFinished = "allFinished",
}

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
  tokenStats?: MCPToolsTokenStats;
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
  relevanceApplied?: boolean;
  contentTokenCount?: number;
  originalTokenCount?: number;
}

export interface ToolCallingTimelineMessage {
  key: string;
  content: string;
  toolCallId: string;
  toolCall: ToolCall;
  reasoningContent: string;
  status: ToolCallStatus.CallingTool;
}

export interface ToolResultErrorTimelineMessage {
  key: string;
  content: string;
  toolCallId: string;
  toolCall: ToolCall;
  reasoningContent: string;
  status: ToolCallStatus.ToolResultError;
}

export interface ToolResultSuccessTimelineMessage {
  key: string;
  toolCallId: string;
  toolCall: ToolCall;
  reasoningContent: string;
  content: string | Record<string, unknown>;
  relevanceApplied?: boolean;
  contentTokenCount?: number;
  originalTokenCount?: number;
  status: ToolCallStatus.ToolResultSuccess;
}

export type ToolCallMessage = ToolCallProcessMessage | ToolCallStartItemMessage | ToolCallEndItemMessage;

export type TimelineMessage =
  | ToolCallingTimelineMessage
  | ToolResultErrorTimelineMessage
  | ToolResultSuccessTimelineMessage;
