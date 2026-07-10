import type { ChatMessage } from "@/interfaces";
import {
  isUserAttachmentBlock,
  type UserAttachmentBlock,
} from "@/interfaces/contentBlock";

const ACTIVE_MENTION_RE = /(^|[\s])@([^\s@]*)$/;

const DISPLAY_NAME_FALLBACK: Record<Exclude<UserAttachmentBlock["type"], "image">, string> = {
  pdf: "document.pdf",
  excel: "spreadsheet.xlsx",
  docx: "document.docx",
  pptx: "presentation.pptx",
  markdown: "document.md",
  text_file: "file.txt",
};

export interface ActiveMention {
  query: string;
  atIndex: number;
}

export function isMentionableAttachment(block: UserAttachmentBlock): boolean {
  return isUserAttachmentBlock(block) && block.type !== "image";
}

export function getAttachmentDisplayName(block: UserAttachmentBlock): string {
  const trimmed = block.name?.trim();
  if (trimmed) {
    return trimmed;
  }
  if (block.type === "image") {
    const ext = block.mime.split("/")[1]?.split("+")[0] || "png";
    return `image.${ext}`;
  }
  return DISPLAY_NAME_FALLBACK[block.type];
}

export function collectMentionableAttachments(options: {
  messages: ChatMessage[];
  currentAttachmentBlocks: UserAttachmentBlock[];
}): UserAttachmentBlock[] {
  const { messages, currentAttachmentBlocks } = options;
  const byId = new Map<string, UserAttachmentBlock>();

  // 当前轮优先：先写入，历史同 id 不会覆盖
  for (const block of currentAttachmentBlocks) {
    if (!isMentionableAttachment(block)) {
      continue;
    }
    byId.set(block.id, block);
  }

  for (const message of messages) {
    if (message.role !== "user") {
      continue;
    }
    for (const block of message.contentBlocks) {
      if (!isUserAttachmentBlock(block) || !isMentionableAttachment(block)) {
        continue;
      }
      if (!byId.has(block.id)) {
        byId.set(block.id, block);
      }
    }
  }

  return Array.from(byId.values());
}

export function getActiveMention(text: string): ActiveMention | null {
  const match = ACTIVE_MENTION_RE.exec(text);
  if (!match) {
    return null;
  }
  const prefix = match[1] ?? "";
  return {
    query: match[2] ?? "",
    atIndex: match.index + prefix.length,
  };
}

export function filterMentionableByQuery(
  attachments: UserAttachmentBlock[],
  query: string
): UserAttachmentBlock[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return attachments;
  }
  return attachments.filter(block => getAttachmentDisplayName(block).toLowerCase().includes(normalized));
}

export function toSuggestionItems(
  attachments: UserAttachmentBlock[]
): Array<{ value: string; label: string }> {
  return attachments.map(block => ({
    value: block.id,
    label: getAttachmentDisplayName(block),
  }));
}

export function applyMentionToText(
  text: string,
  atIndex: number,
  query: string,
  displayName: string
): string {
  const before = text.slice(0, atIndex);
  const after = text.slice(atIndex + 1 + query.length);
  return `${before}@${displayName} ${after}`;
}
