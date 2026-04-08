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
  content?: string;
  structuredContentForDisplay?: WebSearchDisplayItem[];
  summary?: string;
}

export interface WebSearchResultItem {
  title?: string;
  url?: string;
  score?: number;
  favicon?: string;
}

export interface WebSearchDisplayItem {
  query?: string;
  results: WebSearchResultItem[];
}

export enum ContentBlockRenderStatus {
  Start = 1,
  Streaming = 2,
  StreamFinished = 3,
  Running = 4,
  Success = 5,
  Error = 6,
  Done = 100,
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
