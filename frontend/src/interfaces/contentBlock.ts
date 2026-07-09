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
  serverName?: string;
  mcpToolName?: string;
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
  structuredContentForDisplay?: ToolResultDisplayItem[];
  summary?: string;
}

export interface ImageBlock {
  id: string;
  type: "image";
  url: string;
  storageKey?: string;
  storageVersion?: number;
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
  storageKey?: string;
  storageVersion?: number;
  derivedFromId?: string;
  derivedKind?: string;
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
  storageKey?: string;
  storageVersion?: number;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 application/pdf */
  mime: "application/pdf";
  /** PDF 转写得到的 Markdown 预览块（无则缺省） */
  markdown?: MarkdownBlock | null;
}

export interface ExcelBlock {
  id: string;
  type: "excel";
  url: string;
  storageKey?: string;
  storageVersion?: number;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 xlsx 的 MIME */
  mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  /** Excel 转写得到的 Markdown 预览块（无则缺省） */
  markdown?: MarkdownBlock | null;
}

export interface DocxBlock {
  id: string;
  type: "docx";
  url: string;
  storageKey?: string;
  storageVersion?: number;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 docx 的 MIME */
  mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  /** Word 转写得到的 Markdown 预览块（无则缺省） */
  markdown?: MarkdownBlock | null;
}

export interface PptxBlock {
  id: string;
  type: "pptx";
  url: string;
  storageKey?: string;
  storageVersion?: number;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 固定为 pptx 的 MIME */
  mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  /** PowerPoint 转写得到的 Markdown 预览块（无则缺省） */
  markdown?: MarkdownBlock | null;
}

/** 纯文本 / 代码文件附件块（csv、txt、py、js 等）；后端按纯文本存储，无 derived markdown */
export interface TextFileBlock {
  id: string;
  type: "text_file";
  url: string;
  storageKey?: string;
  storageVersion?: number;
  /** 展示用文件名（服务端已安全化）；历史消息可能缺省 */
  name?: string;
  /** 落盘文件字节数 */
  size: number;
  /** 如 text/csv、text/plain */
  mime: string;
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
  /** 打开预览时默认选中的文件（会话相对路径，如 outputs/report.md） */
  selectedFilePath?: string;
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

export interface ShellExecDisplayItem {
  type: "shell_exec";
  exitCode: number;
  stdout?: string;
  stderr?: string;
  timedOut?: boolean;
  outputTruncated?: boolean;
  blocked?: boolean;
  blockReason?: string;
  durationMs?: number;
}

export type ToolResultDisplayItem = WebSearchDisplayItem | ShellExecDisplayItem;

export function isShellExecDisplayItem(item: ToolResultDisplayItem): item is ShellExecDisplayItem {
  return "type" in item && item.type === "shell_exec";
}

export function isWebSearchDisplayItem(item: ToolResultDisplayItem): item is WebSearchDisplayItem {
  return !("type" in item) && Array.isArray(item.results);
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
  | ExcelBlock
  | DocxBlock
  | PptxBlock
  | MarkdownBlock
  | TextFileBlock;

/** 侧栏可预览的内容块（支持 PDF、Excel、Word、PowerPoint、文本/代码、HTML、代码运行结果与工作区项目） */
export type PreviewableBlock =
  | PdfBlock
  | ExcelBlock
  | DocxBlock
  | PptxBlock
  | HtmlBlock
  | CodeExecBlock
  | ProjectBlock
  | MarkdownBlock
  | TextFileBlock;
export type UserContentBlock =
  | TextBlock
  | ImageBlock
  | PdfBlock
  | ExcelBlock
  | DocxBlock
  | PptxBlock
  | MarkdownBlock
  | TextFileBlock;
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
      serverName?: string;
      mcpToolName?: string;
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
  return (
    block.type === "image" ||
    block.type === "pdf" ||
    block.type === "excel" ||
    block.type === "docx" ||
    block.type === "pptx" ||
    block.type === "markdown" ||
    block.type === "text_file"
  );
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
