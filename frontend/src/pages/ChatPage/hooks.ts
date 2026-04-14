import { emitter, EventType } from "@/events";
import { ChatInputFormValues, ChatMessage as ChatMessageType } from "@/interfaces";
import { PdfBlock } from "@/interfaces/contentBlock";
import { useMemoizedFn } from "ahooks";
import type { FormInstance } from "antd";
import { useState } from "react";

interface UsePdfPreviewHandlersParams {
  isSmallScreen: boolean;
}

interface UseChatMessageHandlersParams {
  form: FormInstance<ChatInputFormValues>;
  conversationId: string;
  sendMessage: (values: ChatInputFormValues, options: { index: number }) => void;
  reSendMessage: (index: number, message: ChatMessageType, values: ChatInputFormValues) => void;
  abortMessage: (conversationId: string) => void;
  deleteMessage: (messageId: string) => void | Promise<void>;
}

export const useChatMessageHandlers = ({
  form,
  conversationId,
  sendMessage,
  reSendMessage,
  abortMessage,
  deleteMessage,
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

  return {
    handleEditMessage,
    handleReSend,
    handleAbortMessage,
    handleDeleteMessage,
  };
};

export const usePdfPreviewHandlers = ({ isSmallScreen }: UsePdfPreviewHandlersParams) => {
  const [previewingPdf, setPreviewingPdf] = useState<PdfBlock | null>(null);
  const [rightPanelSize, setRightPanelSize] = useState<number | string>(0);

  const handlePreviewPdf = useMemoizedFn((block: PdfBlock) => {
    emitter.emit(EventType.ChangeSidebarCollapse, true);
    setRightPanelSize(prev => (prev === 0 ? "40%" : prev));
    setPreviewingPdf(block);
  });

  const handleClosePreviewPdf = useMemoizedFn(() => {
    if (!isSmallScreen) {
      emitter.emit(EventType.ChangeSidebarCollapse, false);
    }
    setPreviewingPdf(null);
    setRightPanelSize(0);
  });

  const handleSplitterResize = useMemoizedFn((sizes: number[]) => {
    if (!previewingPdf) {
      return;
    }
    const nextRightPanelSize = sizes[1];
    if (typeof nextRightPanelSize === "number") {
      setRightPanelSize(nextRightPanelSize);
    }
  });

  return {
    previewingPdf,
    rightPanelSize,
    handlePreviewPdf,
    handleClosePreviewPdf,
    handleSplitterResize,
  };
};
