import { isUserAttachmentBlock, type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import { GetProp } from "antd";
import { ButtonState } from "./constant";

export const MAX_CHAT_ATTACHMENTS = 5;
export const MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024;
export const CHAT_ATTACHMENT_ACCEPT = "image/*,.pdf,application/pdf";
export const CHAT_ATTACHMENT_TOOLTIP = "支持图片和 PDF，单文件不超过 10MB，最多 5 个附件";

const IMAGE_EXT_RE = /\.(jpe?g|png|gif|webp)$/i;
const PDF_EXT_RE = /\.pdf$/i;

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

export function isSupportedChatAttachment(file: File) {
  const fileType = file.type.toLowerCase();
  const fileName = file.name.toLowerCase();
  if (fileType.startsWith("image/") || IMAGE_EXT_RE.test(fileName)) {
    return true;
  }
  return fileType === "application/pdf" || PDF_EXT_RE.test(fileName);
}

export function getChatAttachmentValidationError(file: File, currentCount: number) {
  if (currentCount >= MAX_CHAT_ATTACHMENTS) {
    return `最多上传 ${MAX_CHAT_ATTACHMENTS} 个附件`;
  }
  if (!isSupportedChatAttachment(file)) {
    return "仅支持 JPEG、PNG、GIF、WebP 图片和 PDF";
  }
  if (file.size > MAX_CHAT_ATTACHMENT_BYTES) {
    return "单个附件不能超过 10MB";
  }
  return null;
}

export function isButtonDisabled(buttonState: ButtonState) {
  return buttonState === ButtonState.WaitingType;
}

export function isStreamingState(buttonState: ButtonState) {
  return buttonState === ButtonState.Streaming;
}
