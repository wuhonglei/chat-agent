import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useChatMessage, useChatState } from "@/hooks";
import { useMemoizedFn } from "ahooks";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
} from "@/interfaces";
import { Form } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import { SourceData } from "@/interfaces";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";
import { useParams } from "react-router-dom";
import { useCachedRequest, useConversationInfo } from "@/hooks/chat";
import TopHeader from "@/components/Chat/TopHeader";

const ChatPage: React.FC = () => {
  const params = useParams<{ conversationId: string }>();
  const urlConversationId = params.conversationId!;

  // 使用 conversationInfo 确保与 store 状态同步
  const conversationInfo = useConversationInfo(urlConversationId);
  const conversationId = conversationInfo?.id || urlConversationId;

  const { sendMessage, reSendMessage, abortMessage } = useChatMessage({
    conversationId,
  });
  const { isStreaming, isLoading, isReasoning, isCallingTools } =
    useChatState(conversationId);
  const [sourceData, setSourceData] = useState<SourceData | undefined>();
  const [form] = Form.useForm<ChatInputFormValues>();

  useCachedRequest(conversationId, conversationInfo);

  const handleSourceClick = useMemoizedFn(
    (index: number, message: ChatMessageType) => {
      if (sourceData?.index === index) {
        setSourceData(undefined);
      } else {
        setSourceData({ index, sources: message.sources || [] });
      }
    }
  );

  const handleEditMessage = useMemoizedFn((index: number, content: string) => {
    sendMessage({ ...form.getFieldsValue(), content }, { index });
  });

  const handleReSend = useMemoizedFn(
    (index: number, message: ChatMessageType) => {
      reSendMessage(index, message, form.getFieldsValue());
    }
  );

  const handleCloseSource = useMemoizedFn(() => {
    setSourceData(undefined);
  });

  return (
    <section className="h-full flex flex-col">
      <TopHeader conversationInfo={conversationInfo} />
      <main className="flex-1 flex">
        {/* Chat area */}
        <div
          className={classNames(
            "flex-1 flex flex-col h-full bg-white",
            styles.container
          )}
        >
          {/* 渲染消息列表 */}
          <ChatMessageList
            isLoading={isLoading}
            onReSend={handleReSend}
            isStreaming={isStreaming}
            isReasoning={isReasoning}
            isCallingTools={isCallingTools}
            conversationId={conversationId}
            onSourceClick={handleSourceClick}
            onEditMessage={handleEditMessage}
            className={styles["markdown-container"]}
          />
          {/* Input area */}
          <ChatInput
            form={form}
            onSend={sendMessage}
            onStop={abortMessage}
            isStreaming={isStreaming}
            className={styles["input-container"]}
          />
          <div className="mx-auto py-1.5 text-gray-300 text-xs">
            内容由 AI 生成，请仔细甄别
          </div>
        </div>
        {/* Sources panel */}
        <SourceSider sourceData={sourceData} onClose={handleCloseSource} />
      </main>
    </section>
  );
};

export default React.memo(ChatPage);
