import { emitter, EventType } from "@/events";
import { ChatInputFormValues, ChatMessage as ChatMessageType, MessageFeedbackValue } from "@/interfaces";
import type { PreviewableBlock } from "@/interfaces/contentBlock";
import { useMemoizedFn } from "ahooks";
import type { FormInstance } from "antd";
import { useMemo, useState } from "react";

interface UseBlockPreviewHandlersParams {
  isSmallScreen: boolean;
}

interface UseChatMessageHandlersParams {
  form: FormInstance<ChatInputFormValues>;
  conversationId: string;
  sendMessage: (values: ChatInputFormValues, options: { index: number }) => void;
  reSendMessage: (index: number, message: ChatMessageType, values: ChatInputFormValues) => void;
  abortMessage: (conversationId: string) => void;
  deleteMessage: (messageId: string) => void | Promise<void>;
  updateMessageFeedback: (messageId: string, value: MessageFeedbackValue) => Promise<void>;
}

export const useChatMessageHandlers = ({
  form,
  conversationId,
  sendMessage,
  reSendMessage,
  abortMessage,
  deleteMessage,
  updateMessageFeedback,
}: UseChatMessageHandlersParams) => {
  const handleEditMessage = useMemoizedFn((index: number, content: string) => {
    sendMessage({ ...form.getFieldsValue(), content }, { index });
  });

  const handleReSend = useMemoizedFn((index: number, message: ChatMessageType) => {
    reSendMessage(index, message, form.getFieldsValue());
  });

  const handleAbortMessage = useMemoizedFn(() => {
    abortMessage(conversationId);
  });

  const handleDeleteMessage = useMemoizedFn((messageId: string) => {
    return deleteMessage(messageId);
  });

  const handleUpdateMessageFeedback = useMemoizedFn((messageId: string, value: MessageFeedbackValue) => {
    return updateMessageFeedback(messageId, value);
  });

  return {
    handleEditMessage,
    handleReSend,
    handleAbortMessage,
    handleDeleteMessage,
    handleUpdateMessageFeedback,
  };
};

function getDefaultPreviewPanelWidthPx(isSmallScreen: boolean): number {
  if (typeof window === "undefined") {
    return 400;
  }
  const ratio = isSmallScreen ? 1 : 0.6;
  return Math.max(280, Math.round(window.innerWidth * ratio));
}

export const useBlockPreviewHandlers = ({ isSmallScreen }: UseBlockPreviewHandlersParams) => {
  const [previewBlock, setPreviewBlock] = useState<PreviewableBlock | null>(null);
  const [previewPanelSize, setPreviewPanelSize] = useState(0);

  const handleOpenBlockPreview = useMemoizedFn((block: PreviewableBlock) => {
    emitter.emit(EventType.ChangeSidebarCollapse, true);
    setPreviewPanelSize(prev => (prev === 0 ? getDefaultPreviewPanelWidthPx(isSmallScreen) : prev));
    setPreviewBlock(block);
  });

  const handleCloseBlockPreview = useMemoizedFn(() => {
    if (!isSmallScreen) {
      emitter.emit(EventType.ChangeSidebarCollapse, false);
    }
    setPreviewBlock(null);
    setPreviewPanelSize(0);
  });

  const handleSplitterResize = useMemoizedFn((sizes: number[]) => {
    if (!previewBlock) {
      return;
    }
    const nextPreviewPanelSize = sizes[1];
    if (typeof nextPreviewPanelSize === "number") {
      setPreviewPanelSize(nextPreviewPanelSize);
    }
  });

  return {
    previewBlock,
    previewPanelSize,
    handleOpenBlockPreview,
    handleCloseBlockPreview,
    handleSplitterResize,
  };
};

export const useHasImageMessage = (messages: ChatMessageType[]): boolean => {
  return useMemo(
    () => messages.some(message => message.contentBlocks.some(block => block.type === "image")),
    [messages]
  );
};
