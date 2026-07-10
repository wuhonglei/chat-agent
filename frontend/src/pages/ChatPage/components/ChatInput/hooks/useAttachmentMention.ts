import type { ChatMessage } from "@/interfaces";
import type { UserAttachmentBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { GetProp } from "antd";
import { useMemo, useState } from "react";
import {
  applyMentionToText,
  collectMentionableAttachments,
  filterMentionableByQuery,
  getActiveMention,
  getAttachmentDisplayName,
  toSuggestionItems,
} from "../attachmentMention";
import { getAttachmentBlocks } from "../util";

export interface UseAttachmentMentionOptions {
  messages: ChatMessage[];
  attachmentItems: GetProp<AttachmentsProps, "items">;
}

export type MentionTriggerInfo = { query: string };

export function useAttachmentMention({ messages, attachmentItems }: UseAttachmentMentionOptions) {
  const [mentionedBlocks, setMentionedBlocks] = useState<UserAttachmentBlock[]>([]);

  const mentionableAttachments = useMemo(() => {
    return collectMentionableAttachments({
      messages,
      currentAttachmentBlocks: getAttachmentBlocks(attachmentItems),
    });
  }, [messages, attachmentItems]);

  const getSuggestionItems = useMemoizedFn((query: string) => {
    return toSuggestionItems(filterMentionableByQuery(mentionableAttachments, query));
  });

  const handleContentChange = useMemoizedFn(
    (
      nextValue: string,
      onChange: ((value: string) => void) | undefined,
      onTrigger: (info: MentionTriggerInfo | false) => void
    ) => {
      onChange?.(nextValue);
      if (mentionableAttachments.length === 0) {
        onTrigger(false);
        return;
      }
      const active = getActiveMention(nextValue);
      if (active) {
        onTrigger({ query: active.query });
      } else {
        onTrigger(false);
      }
    }
  );

  const handleMentionSelect = useMemoizedFn(
    (blockId: string, currentValue: string, onChange: ((value: string) => void) | undefined) => {
      const block = mentionableAttachments.find(item => item.id === blockId);
      if (!block) {
        return;
      }
      const active = getActiveMention(currentValue);
      if (!active) {
        return;
      }
      const displayName = getAttachmentDisplayName(block);
      const nextValue = applyMentionToText(currentValue, active.atIndex, active.query, displayName);
      onChange?.(nextValue);
      setMentionedBlocks(prev => (prev.some(item => item.id === block.id) ? prev : [...prev, block]));
    }
  );

  const resetMentionedBlocks = useMemoizedFn(() => {
    setMentionedBlocks([]);
  });

  return {
    mentionedBlocks,
    mentionableAttachments,
    getSuggestionItems,
    handleContentChange,
    handleMentionSelect,
    resetMentionedBlocks,
  };
}
