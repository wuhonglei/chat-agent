import { useChatMessage, useChatState, useIsSmallScreen } from "@/hooks";
import { useCachedRequest, useConversationInfo } from "@/hooks/chat";
import { ChatInputFormValues } from "@/interfaces";
import { Form, Splitter } from "antd";
import classNames from "classnames";
import React from "react";
import { useParams } from "react-router-dom";
import ChatInput from "./components/ChatInput";
import { ChatMessageList } from "./components/ChatMessage";
import PdfPreviewPanel from "./components/PdfPreviewPanel";
import TopHeader from "./components/TopHeader";
import { useChatMessageHandlers, usePdfPreviewHandlers } from "./hooks";
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
  const { previewingPdf, rightPanelSize, handlePreviewPdf, handleClosePreviewPdf, handleSplitterResize } =
    usePdfPreviewHandlers({ isSmallScreen });
  const { handleEditMessage, handleReSend, handleAbortMessage, handleDeleteMessage } = useChatMessageHandlers({
    form,
    conversationId,
    sendMessage,
    reSendMessage,
    abortMessage,
    deleteMessage,
  });

  useCachedRequest(conversationId, conversationInfo);

  return (
    <section className="h-full min-h-0">
      <Splitter style={{ height: "100%", width: "100%" }} onResize={handleSplitterResize}>
        <Splitter.Panel defaultSize="60%" min={previewingPdf ? "40%" : 0}>
          <section className="h-full min-h-0 flex flex-col">
            <TopHeader conversationInfo={conversationInfo} />
            <main className="flex-1 min-h-0 flex">
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
            </main>
          </section>
        </Splitter.Panel>
        <Splitter.Panel
          size={previewingPdf ? rightPanelSize : 0}
          min={previewingPdf ? "20%" : 0}
          max={previewingPdf ? "60%" : 0}
          resizable={Boolean(previewingPdf)}
        >
          {previewingPdf ? (
            <PdfPreviewPanel
              pdfUrl={previewingPdf.url}
              pdfName={previewingPdf.name}
              isSmallScreen={isSmallScreen}
              onClose={handleClosePreviewPdf}
            />
          ) : null}
        </Splitter.Panel>
      </Splitter>
    </section>
  );
};

export default React.memo(ChatPage);
