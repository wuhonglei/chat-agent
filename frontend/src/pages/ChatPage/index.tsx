import { useChatMessage, useChatState, useIsSmallScreen } from "@/hooks";
import { useCachedRequest, useConversationInfo } from "@/hooks/chat";
import { ChatInputFormValues, ChatMessage as ChatMessageType } from "@/interfaces";
import { PdfBlock } from "@/interfaces/contentBlock";
import { useMemoizedFn } from "ahooks";
import { Form, Splitter } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import { useParams } from "react-router-dom";
import ChatInput from "./components/ChatInput";
import { ChatMessageList } from "./components/ChatMessage";
import PdfPreviewPanel from "./components/PdfPreviewPanel";
import TopHeader from "./components/TopHeader";
import styles from "./index.module.css";

const ChatPage: React.FC = () => {
  const params = useParams<{ conversationId: string }>();
  const urlConversationId = params.conversationId!;

  // 使用 conversationInfo 确保与 store 状态同步
  const conversationInfo = useConversationInfo(urlConversationId);
  const conversationId = conversationInfo?.id || urlConversationId;

  const { sendMessage, reSendMessage, abortMessage, deleteMessage } = useChatMessage({
    conversationId,
  });
  const { isStreaming, isLoading } = useChatState(conversationId);
  const isSmallScreen = useIsSmallScreen();
  const [form] = Form.useForm<ChatInputFormValues>();
  const [previewingPdf, setPreviewingPdf] = useState<PdfBlock | null>(null);

  useCachedRequest(conversationId, conversationInfo);

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

  const handlePreviewPdf = useMemoizedFn((block: PdfBlock) => {
    setPreviewingPdf(block);
  });

  const handleClosePreviewPdf = useMemoizedFn(() => {
    setPreviewingPdf(null);
  });

  const chatContent = (
    <div className={classNames("flex-1 min-w-0 flex flex-col h-full bg-white", styles.container)}>
      {/* 渲染消息列表 */}
      <ChatMessageList
        isLoading={isLoading}
        onReSend={handleReSend}
        isStreaming={isStreaming}
        conversationId={conversationId}
        onEditMessage={handleEditMessage}
        onDeleteMessage={handleDeleteMessage}
        onPreviewPdf={handlePreviewPdf}
        className={styles["markdown-container"]}
      />
      {/* Input area */}
      <ChatInput
        form={form}
        onSend={sendMessage}
        isStreaming={isStreaming}
        onStop={handleAbortMessage}
        className={styles["input-container"]}
      />
      <div className="mx-auto py-1 md:py-1.5 text-black-quaternary text-xs">内容由 AI 生成，请仔细甄别</div>
    </div>
  );

  return (
    <section className="h-full flex flex-col">
      <TopHeader conversationInfo={conversationInfo} />
      <main className="flex-1 min-h-0 flex">
        {previewingPdf ? (
          <Splitter style={{ height: "100%", width: "100%" }}>
            <Splitter.Panel defaultSize="68%" min="40%">
              {chatContent}
            </Splitter.Panel>
            <Splitter.Panel defaultSize="32%" min="20%" max="60%">
              <PdfPreviewPanel
                pdfUrl={previewingPdf.url}
                pdfName={previewingPdf.name}
                isSmallScreen={isSmallScreen}
                onClose={handleClosePreviewPdf}
              />
            </Splitter.Panel>
          </Splitter>
        ) : (
          chatContent
        )}
      </main>
    </section>
  );
};

export default React.memo(ChatPage);
