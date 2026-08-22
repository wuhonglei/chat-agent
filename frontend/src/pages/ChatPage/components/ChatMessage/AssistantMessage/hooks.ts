import { MessageStatus, type IterationCheckpoint } from "@/interfaces/chat";
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

interface UseIterationCheckpointActionsOptions {
  checkpoint: IterationCheckpoint | undefined;
  isLastMessage: boolean;
  isStreaming: boolean;
  messageStatus: MessageStatus;
  onContinue?: () => void;
  onSummarize?: () => void;
}

interface IterationCheckpointActionsState {
  checkpoint: IterationCheckpoint;
  onContinue: () => void;
  onSummarize: () => void;
}

export function useIterationCheckpointActions(
  options: UseIterationCheckpointActionsOptions
): IterationCheckpointActionsState | null {
  const { checkpoint, isLastMessage, isStreaming, messageStatus, onContinue, onSummarize } = options;

  if (
    !checkpoint ||
    !isLastMessage ||
    isStreaming ||
    messageStatus !== MessageStatus.Done ||
    !onContinue ||
    !onSummarize
  ) {
    return null;
  }

  return { checkpoint, onContinue, onSummarize };
}
