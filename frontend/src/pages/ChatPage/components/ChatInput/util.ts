import { isUserAttachmentBlock, type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import type { UploadFile } from "antd";
import { GetProp } from "antd";
import { ButtonState } from "./constant";

export const MAX_CHAT_ATTACHMENTS = 5;
export const MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024;
export const CHAT_ATTACHMENT_ACCEPT = "image/*,.pdf,application/pdf,.md,.markdown,text/markdown";
export const CHAT_ATTACHMENT_ACCEPT_PDF_ONLY = ".pdf,application/pdf";

const IMAGE_EXT_RE = /\.(jpe?g|png|gif|webp)$/i;
const PDF_EXT_RE = /\.pdf$/i;
const MARKDOWN_EXT_RE = /\.(md|markdown)$/i;

export function isImageFile(file: Pick<File, "type" | "name">) {
  const fileType = file.type.toLowerCase();
  const fileName = file.name.toLowerCase();
  return fileType.startsWith("image/") || IMAGE_EXT_RE.test(fileName);
}

export function getAttachmentBlocks(items: GetProp<AttachmentsProps, "items"> | undefined): UserAttachmentBlock[] {
  if (!items?.length) {
    return [];
  }
  const out: UserAttachmentBlock[] = [];
  for (const item of items) {
    if (item.status !== "done" || item.response == null) {
      continue;
    }
    const r = item.response as unknown;
    if (typeof r === "object" && r !== null && "type" in r && isUserAttachmentBlock(r as UserAttachmentBlock)) {
      out.push(r as UserAttachmentBlock);
    }
  }
  return out;
}

export function areAttachmentsReady(items: GetProp<AttachmentsProps, "items"> | undefined): boolean {
  if (!items?.length) {
    return true;
  }
  return getAttachmentBlocks(items).length === items.length;
}

export function isSupportedChatAttachment(file: File) {
  const fileType = file.type.toLowerCase();
  if (isImageFile(file)) {
    return true;
  }
  if (fileType === "application/pdf" || PDF_EXT_RE.test(file.name.toLowerCase())) {
    return true;
  }
  return MARKDOWN_EXT_RE.test(file.name.toLowerCase()) || fileType === "text/markdown";
}

export function getChatAttachmentValidationError(file: File, currentCount: number) {
  if (currentCount >= MAX_CHAT_ATTACHMENTS) {
    return `最多上传 ${MAX_CHAT_ATTACHMENTS} 个附件`;
  }
  if (!isSupportedChatAttachment(file)) {
    return "仅支持 JPEG、PNG、GIF、WebP 图片、PDF 和 Markdown";
  }
  if (file.size > MAX_CHAT_ATTACHMENT_BYTES) {
    return "单个附件不能超过 10MB";
  }
  return null;
}

export function isStreamingState(buttonState: ButtonState) {
  return buttonState === ButtonState.Streaming;
}

function isImageUploadItem(item: UploadFile<UserAttachmentBlock>) {
  if (item.type?.startsWith("image/")) {
    return true;
  }
  if (item.name && IMAGE_EXT_RE.test(item.name.toLowerCase())) {
    return true;
  }
  if (item.originFileObj && isImageFile(item.originFileObj)) {
    return true;
  }
  if (item.response && typeof item.response === "object") {
    return (item.response as UserAttachmentBlock).type === "image";
  }
  return false;
}

export function attachmentItemsHasImage(items: GetProp<AttachmentsProps, "items"> | undefined) {
  if (!items?.length) {
    return false;
  }
  return items.some(item => isImageUploadItem(item as UploadFile<UserAttachmentBlock>));
}
