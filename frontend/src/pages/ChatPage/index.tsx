import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useChatMessage, useNewConversation } from "@/hooks";
import { useMemoizedFn, useRequest } from "ahooks";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
} from "@/interfaces";
import { Form } from "antd";
import classNames from "classnames";
import React, { useEffect, useState } from "react";
import { SourceData } from "@/interfaces";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";
import { useParams, useNavigate } from "react-router-dom";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { shallowEqual } from "react-redux";
import { setMessages } from "@/store/slices/chatSlice";
import { chatAPI } from "@/services";

const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { conversationId } = useParams<{ conversationId: string }>();
  const { sendMessage, reSendMessage, abortMessage } = useChatMessage({
    conversationId: conversationId as string,
  });
  const { isStreaming, isLoading, isReasoning, isCallingTools } =
    useAppSelector(state => {
      const chatState = state.chat;
      return {
        isStreaming: chatState.isStreaming,
        isLoading: chatState.isLoading,
        isReasoning: chatState.isReasoning,
        isCallingTools: chatState.isCallingTools,
      };
    }, shallowEqual);
  const [sourceData, setSourceData] = useState<SourceData | undefined>();
  const [form] = Form.useForm<ChatInputFormValues>();

  // 页面刷新后清除 isNewConversation 状态
  const { cacheData: conversationState, clearCacheData } = useNewConversation();
  useRequest(() => chatAPI.getConversationMessages(conversationId as string), {
    ready: !conversationState.isNewConversation && !!conversationId, // 如果是新对话，则无需加载历史消息
    refreshDeps: [conversationId],
    onSuccess: data => {
      dispatch(setMessages(data));
    },
    onError: error => {
      if ((error as any).code === 404) {
        navigate("/chat", { replace: true });
      }
    },
  });

  useEffect(() => {
    // 如果是新对话，则发送消息
    if (conversationState.isNewConversation) {
      clearCacheData();
      sendMessage(conversationState.values, {
        createdBy: conversationState.createdBy,
      });
    }
  }, [conversationState, sendMessage, clearCacheData]);

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

  const chatInputProps = {
    form,
    onStop: abortMessage,
    onSend: sendMessage,
    isStreaming: isStreaming,
  };

  return (
    <div className="flex h-full">
      {/* Chat area */}
      <div
        className={classNames(
          "flex-1 flex flex-col h-full bg-white pb-7",
          styles.container
        )}
      >
        <ChatMessageList
          isLoading={isLoading}
          isStreaming={isStreaming}
          isReasoning={isReasoning}
          isCallingTools={isCallingTools}
          onReSend={handleReSend}
          onSourceClick={handleSourceClick}
          onEditMessage={handleEditMessage}
          className={styles["markdown-container"]}
        />
        {/* Input area */}
        <ChatInput {...chatInputProps} className={styles["input-container"]} />
      </div>
      {/* Sources panel */}
      <SourceSider sourceData={sourceData} onClose={handleCloseSource} />
    </div>
  );
};

export default React.memo(ChatPage);
