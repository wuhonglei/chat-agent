import { useChatMessage, useChatState } from "@/hooks";
import { useCachedRequest, useConversationInfo } from "@/hooks/chat";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
} from "@/interfaces";
import { useMemoizedFn } from "ahooks";
import { Form } from "antd";
import classNames from "classnames";
import React from "react";
import { useParams } from "react-router-dom";
import ChatInput from "./components/ChatInput";
import { ChatMessageList } from "./components/ChatMessage";
import TopHeader from "./components/TopHeader";
import styles from "./index.module.css";

const ChatPage: React.FC = () => {
  const params = useParams<{ conversationId: string }>();
  const urlConversationId = params.conversationId!;

  // 使用 conversationInfo 确保与 store 状态同步
  const conversationInfo = useConversationInfo(urlConversationId);
  const conversationId = conversationInfo?.id || urlConversationId;

  const { sendMessage, reSendMessage, abortMessage } = useChatMessage({
    conversationId,
  });
  const {
    isStreaming,
    isLoading,
    isReasoning,
    isCallingMcpTools,
    isCallingComponentTools,
  } = useChatState(conversationId);
  const [form] = Form.useForm<ChatInputFormValues>();

  useCachedRequest(conversationId, conversationInfo);

  const handleEditMessage = useMemoizedFn((index: number, content: string) => {
    sendMessage({ ...form.getFieldsValue(), content }, { index });
  });

  const handleReSend = useMemoizedFn(
    (index: number, message: ChatMessageType) => {
      reSendMessage(index, message, form.getFieldsValue());
    }
  );

  const handleAbortMessage = useMemoizedFn(() => {
    abortMessage(conversationId);
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
            isCallingMcpTools={isCallingMcpTools}
            isCallingComponentTools={isCallingComponentTools}
            conversationId={conversationId}
            onEditMessage={handleEditMessage}
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
          <div className="mx-auto py-1 md:py-1.5 text-black-quaternary text-xs">
            内容由 AI 生成，请仔细甄别
          </div>
        </div>
      </main>
    </section>
  );
};

export default React.memo(ChatPage);
