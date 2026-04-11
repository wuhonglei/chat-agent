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

export interface ImageBlock {
  id: string;
  type: "image";
  url: string;
  /** 字节大小 */
  size: number;
  /** 如 image/jpeg */
  mime: string;
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

export type ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock | ImageBlock;
export type UserContentBlock = TextBlock | ImageBlock;

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

/** 用户消息仅含文本块时可编辑（含图片等非文本块时不允许编辑） */
export function isUserMessageContentTextOnly(blocks: ContentBlock[] | undefined): boolean {
  return (blocks ?? []).every(block => block.type === "text");
}

/** 组装发往后端的用户 content_blocks：先文本块，再按顺序追加附件块（图片、PDF 等） */
export function buildUserContentBlocks(
  content: string,
  attachmentBlocks: ImageBlock[] | undefined
): UserContentBlock[] {
  const blocks: UserContentBlock[] = [];
  const text = content.trim();
  if (text) {
    blocks.push({
      id: `cb_user_text_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      type: "text",
      text,
    });
  }
  if (attachmentBlocks?.length) {
    for (const block of attachmentBlocks) {
      blocks.push(block);
    }
  }
  return blocks;
}

export function getMessageThinkingFromBlocks(blocks: ContentBlock[] | undefined): string {
  return (blocks || [])
    .filter((block): block is ThinkingBlock => block.type === "thinking")
    .map(block => block.text)
    .join("");
}
