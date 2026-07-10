import type { ChatMessage } from "@/interfaces";
import type { UserAttachmentBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { GetProp } from "antd";
import { useMemo, useState } from "react";
import {
  buildMentionTagSlot,
  collectMentionableAttachments,
  filterMentionableByQuery,
  getActiveMention,
  getMentionReplaceCharacters,
  toSuggestionItems,
} from "../attachmentMention";
import { getAttachmentBlocks } from "../util";

export interface UseAttachmentMentionOptions {
  messages: ChatMessage[];
  attachmentItems: GetProp<AttachmentsProps, "items">;
}

export type MentionTriggerInfo = { query: string };

export interface MentionSelectResult {
  block: UserAttachmentBlock;
  tagSlot: ReturnType<typeof buildMentionTagSlot>;
  replaceCharacters: string;
}

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

  const handleMentionSelect = useMemoizedFn((blockId: string, currentValue: string): MentionSelectResult | null => {
    const block = mentionableAttachments.find(item => item.id === blockId);
    if (!block) {
      return null;
    }
    const active = getActiveMention(currentValue);
    if (!active) {
      return null;
    }
    setMentionedBlocks(prev => (prev.some(item => item.id === block.id) ? prev : [...prev, block]));
    return {
      block,
      tagSlot: buildMentionTagSlot(block),
      replaceCharacters: getMentionReplaceCharacters(active.query),
    };
  });

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
