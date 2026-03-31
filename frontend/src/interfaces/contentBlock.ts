export interface TextBlock {
  id: string;
  type: "text";
  text: string;
}

export interface ThinkingBlock {
  id: string;
  type: "thinking";
  text: string;
}

export interface ToolUseBlock {
  id: string;
  type: "tool_use";
  toolCallId?: string;
  name?: string;
  argumentsText: string;
  argumentsJson?: Record<string, unknown>;
}

export interface ToolResultBlock {
  id: string;
  type: "tool_result";
  toolCallId: string;
  toolUseId: string;
  isError: boolean;
  content: string;
  summary?: string;
}

export type ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock;

export type ContentBlockEvent =
  | { op: "append"; block: ContentBlock }
  | { op: "delta"; blockId: string; delta: string }
  | {
      op: "tool_delta";
      blockId: string;
      argumentsDelta: string;
      toolCallId?: string;
      name?: string;
    }
  | { op: "finalize_round" }
  | { op: "done" };

export function getMessageTextFromBlocks(blocks: ContentBlock[] | undefined): string {
  return (blocks || [])
    .filter((block): block is TextBlock => block.type === "text")
    .map(block => block.text)
    .join("");
}

export function getMessageThinkingFromBlocks(blocks: ContentBlock[] | undefined): string {
  return (blocks || [])
    .filter((block): block is ThinkingBlock => block.type === "thinking")
    .map(block => block.text)
    .join("");
}
