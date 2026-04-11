import type { ContentBlock } from "@/interfaces/contentBlock";
import { useMemo } from "react";

export function useAssistantCanDelete(options: {
  isLastMessage: boolean;
  isStreaming: boolean;
  contentBlocks: ContentBlock[] | undefined;
}): boolean {
  const { isLastMessage, isStreaming, contentBlocks } = options;
  return useMemo(() => {
    if (!isLastMessage || isStreaming) return false;
    const blocks = contentBlocks;
    const last = blocks?.[blocks.length - 1];
    return last?.type !== "text";
  }, [isLastMessage, isStreaming, contentBlocks]);
}
