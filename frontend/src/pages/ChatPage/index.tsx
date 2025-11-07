import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useChatMessage } from "@/hooks";
import { useMemoizedFn, useRequest } from "ahooks";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
} from "@/interfaces";
import { Card, Form } from "antd";
import classNames from "classnames";
import React, { useEffect, useState } from "react";
import { SourceData } from "@/interfaces";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";
import WelcomePage from "@/components/Chat/WelcomePage";
import { isEmpty } from "lodash-es";
import { useParams, useNavigate } from "react-router-dom";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { shallowEqual } from "react-redux";
import { registerConversation } from "@/store/slices/conversationSlice";
import { EventType, useEmitter } from "@/events";
import {
  clearCurrentChat,
  getConversationMessages,
} from "@/store/slices/chatSlice";

const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { conversationId } = useParams<{ conversationId?: string }>();
  const { sendMessage, reSendMessage, abortMessage } = useChatMessage({
    conversationId,
  });
  const { isStreaming, isLoading, isReasoning, isCallingTools } =
    useAppSelector(
      state => ({
        isStreaming: state.chat.isStreaming,
        isLoading: state.chat.isLoading,
        isReasoning: state.chat.isReasoning,
        isCallingTools: state.chat.isCallingTools,
      }),
      shallowEqual
    );
  const [sourceData, setSourceData] = useState<SourceData | undefined>();
  const [form] = Form.useForm<ChatInputFormValues>();

  useEmitter(EventType.ChangeConversion, () => {
    abortMessage();
    dispatch(clearCurrentChat());
  });

  useEffect(() => {
    conversationId &&
      dispatch(getConversationMessages(conversationId))
        .unwrap()
        .catch(error => {
          console.info("error", error);
        });
  }, [conversationId, dispatch]);

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
    sendMessage({ ...form.getFieldsValue(), message: content }, index);
  });

  const handleReSend = useMemoizedFn(
    (index: number, message: ChatMessageType) => {
      reSendMessage(index, message, form.getFieldsValue());
    }
  );

  const handleCloseSource = useMemoizedFn(() => {
    setSourceData(undefined);
  });

  const onBeforeSendMessage = useMemoizedFn(
    async (values: ChatInputFormValues) => {
      if (conversationId) {
        return sendMessage(values);
      }
      // 创建会话
      const { id } = await dispatch(registerConversation()).unwrap();
      // 使用新的 conversationId 发送消息
      const sendPromise = sendMessage(values, undefined, id);
      // 更新 URL 到新的会话 ID
      navigate(`/chat/${id}`, { replace: true });
      return sendPromise;
    }
  );

  const chatInputProps = {
    form,
    onStop: abortMessage,
    onSend: sendMessage,
    isLoading: isLoading,
    isStreaming: isStreaming,
  };

  return (
    <div className="flex h-full">
      {/* Chat area */}
      <Card
        className="flex-1"
        classNames={{
          body: classNames("flex flex-col h-full", styles.container),
        }}
        style={{
          border: "none",
        }}
        styles={{
          body: {
            paddingTop: 0,
            paddingLeft: 0,
            paddingRight: 0,
          },
        }}
      >
        {isEmpty(conversationId) ? (
          <WelcomePage
            className={classNames("my-auto pb-12", styles["input-container"])}
          >
            <ChatInput
              {...chatInputProps}
              onSend={onBeforeSendMessage}
              className="w-full shadow-lg"
            />
          </WelcomePage>
        ) : (
          <>
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
            <ChatInput
              {...chatInputProps}
              className={styles["input-container"]}
            />
          </>
        )}
      </Card>
      {/* Sources panel */}
      <SourceSider sourceData={sourceData} onClose={handleCloseSource} />
    </div>
  );
};

export default React.memo(ChatPage);
