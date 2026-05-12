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
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数（经缩放/重编码等处理后的实际大小） */
  size: number;
  /** 如 image/jpeg */
  mime: string;
}

/** 与后端 MarkdownBlock 对齐；可作为独立附件块，也可嵌套在 PdfBlock.markdown */
export interface MarkdownBlock {
  id: string;
  type: "markdown";
  url: string;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 text/markdown */
  mime: "text/markdown";
}

export interface PdfBlock {
  id: string;
  type: "pdf";
  url: string;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 application/pdf */
  mime: "application/pdf";
  /** PDF 转写得到的 Markdown 预览块（无则缺省） */
  markdown?: MarkdownBlock | null;
}

export interface HtmlBlock {
  id: string;
  type: "html";
  content: string;
}

export interface CodeExecStage {
  stdout: string;
  stderr: string;
  output: string;
  code: number | null;
  signal: unknown;
}

export type CodeRuntimeLanguage = "python" | "javascript" | "typescript";

export interface CodeExecBlock {
  id: string;
  type: "code_exec";
  language: CodeRuntimeLanguage;
  code: string;
  version: string;
  run: CodeExecStage;
  compile: CodeExecStage | null;
}

export interface ProjectBlock {
  id: string;
  type: "project";
  workspaceId: string;
  title?: string;
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

export type ContentBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | ToolResultBlock
  | ImageBlock
  | PdfBlock
  | MarkdownBlock;

/** 侧栏可预览的内容块（支持 PDF、HTML、代码运行结果与工作区项目） */
export type PreviewableBlock = PdfBlock | HtmlBlock | CodeExecBlock | ProjectBlock;
export type UserContentBlock = TextBlock | ImageBlock | PdfBlock;
/** 用户消息中的附件块（图片、PDF 等），不含文本块 */
export type UserAttachmentBlock = Exclude<UserContentBlock, TextBlock>;

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

export function hasAttachmentBlocks(blocks: ContentBlock[] | undefined): boolean {
  return (blocks ?? []).some(block => block.type !== "text");
}

export function isUserAttachmentBlock(block: ContentBlock): block is UserAttachmentBlock {
  return block.type === "image" || block.type === "pdf";
}

/** 组装发往后端的用户 content_blocks：先文本块，再按顺序追加附件块（图片、PDF 等） */
export function buildUserContentBlocks(
  content: string,
  attachmentBlocks: UserAttachmentBlock[] | undefined
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
