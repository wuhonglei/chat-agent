import { useChatMessage, useChatState, useIsSmallScreen } from "@/hooks";
import { useCachedRequest, useConversationInfo } from "@/hooks/chat";
import { ChatInputFormValues } from "@/interfaces";
import { Form, Splitter } from "antd";
import classNames from "classnames";
import React, { useMemo } from "react";
import { useParams } from "react-router-dom";
import BlockPreviewPanel from "./components/BlockPreviewPanel";
import ChatInput from "./components/ChatInput";
import { ChatMessageList } from "./components/ChatMessage";
import TopHeader from "./components/TopHeader";
import { BlockPreviewProvider } from "./context/BlockPreviewProvider";
import { useBlockPreviewHandlers, useChatMessageHandlers, useHasImageMessage } from "./hooks";
import styles from "./index.module.css";

const ChatPage: React.FC = () => {
  const params = useParams<{ conversationId: string }>();
  const urlConversationId = params.conversationId!;

  // 使用 conversationInfo 确保与 store 状态同步
  const conversationInfo = useConversationInfo(urlConversationId);
  const conversationId = conversationInfo?.id || urlConversationId;

  const { sendMessage, reSendMessage, abortMessage, deleteMessage, updateMessageFeedback } =
    useChatMessage({
      conversationId,
    });
  const { isStreaming, isLoading, messages } = useChatState(conversationId);
  const hasImageMessage = useHasImageMessage(messages);
  const isSmallScreen = useIsSmallScreen();
  const [form] = Form.useForm<ChatInputFormValues>();
  const {
    previewBlock,
    previewPanelSize,
    handleOpenBlockPreview,
    handleCloseBlockPreview,
    handleSplitterResize,
  } = useBlockPreviewHandlers({ isSmallScreen });
  const {
    handleEditMessage,
    handleReSend,
    handleAbortMessage,
    handleDeleteMessage,
    handleUpdateMessageFeedback,
    handleContinueTask,
    handleSummarizeTask,
  } = useChatMessageHandlers({
    form,
    conversationId,
    sendMessage,
    reSendMessage,
    abortMessage,
    deleteMessage,
    updateMessageFeedback,
  });

  useCachedRequest(conversationId, conversationInfo);

  const blockPreviewContextValue = useMemo(
    () => ({ openPreview: handleOpenBlockPreview }),
    [handleOpenBlockPreview],
  );

  return (
    <section className="h-full min-h-0">
      <BlockPreviewProvider value={blockPreviewContextValue}>
        <Splitter
          onResize={handleSplitterResize}
          styles={{
            root: { height: "100%", width: "100%" },
          }}
          classNames={{
            root: styles["splitter"],
          }}
        >
          <Splitter.Panel>
            <section className="h-full min-h-0 flex flex-col">
              <TopHeader conversationInfo={conversationInfo} />
              <main className="flex-1 min-h-0 flex">
                <div
                  className={classNames(
                    "flex-1 min-w-0 flex flex-col h-full bg-white",
                    styles.container,
                  )}
                >
                  {/* 渲染消息列表 */}
                  <ChatMessageList
                    isLoading={isLoading}
                    onReSend={handleReSend}
                    isStreaming={isStreaming}
                    conversationId={conversationId}
                    onEditMessage={handleEditMessage}
                    onDeleteMessage={handleDeleteMessage}
                    onPreviewBlock={handleOpenBlockPreview}
                    className={styles["markdown-container"]}
                    onUpdateMessageFeedback={handleUpdateMessageFeedback}
                    onContinueTask={handleContinueTask}
                    onSummarizeTask={handleSummarizeTask}
                  />
                  {/* Input area */}
                  <ChatInput
                    conversationId={conversationId}
                    form={form}
                    onSend={sendMessage}
                    isStreaming={isStreaming}
                    hasImageMessage={hasImageMessage}
                    onStop={handleAbortMessage}
                    className={styles["input-container"]}
                  />
                  <div className="mx-auto py-1 md:py-1.5 text-black-quaternary text-xs">
                    内容由 AI 生成，请仔细甄别
                  </div>
                </div>
              </main>
            </section>
          </Splitter.Panel>
          <Splitter.Panel
            className="shadow-xl"
            min={previewBlock ? "20%" : 0}
            max={previewBlock ? "100%" : 0}
            resizable={Boolean(previewBlock)}
            size={previewBlock ? previewPanelSize : 0}
          >
            {previewBlock ? (
              <BlockPreviewPanel
                width={previewPanelSize}
                block={previewBlock}
                onClose={handleCloseBlockPreview}
              />
            ) : null}
          </Splitter.Panel>
        </Splitter>
      </BlockPreviewProvider>
    </section>
  );
};

export default React.memo(ChatPage);
