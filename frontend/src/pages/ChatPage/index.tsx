import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useChatMessage } from "@/hooks";
import { useMemoizedFn } from "ahooks";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
} from "@/interfaces";
import { Card, Form } from "antd";
import classNames from "classnames";
import React, { useMemo, useState } from "react";
import { SourceData } from "@/interfaces";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";
import WelcomePage from "@/components/Chat/WelcomePage";
import { isEmpty } from "lodash-es";

const ChatPage: React.FC = () => {
  const {
    messages,
    isStreaming,
    isLoading,
    isReasoning,
    sendMessage,
    reSendMessage,
    abortMessage,
  } = useChatMessage();
  const [sourceData, setSourceData] = useState<SourceData | undefined>();
  const [form] = Form.useForm<ChatInputFormValues>();

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
            paddingLeft: 0,
            paddingRight: 0,
          },
        }}
      >
        {isEmpty(messages) ? (
          <WelcomePage
            className={classNames("my-auto pb-12", styles["input-container"])}
          >
            <ChatInput {...chatInputProps} className="w-full shadow-lg" />
          </WelcomePage>
        ) : (
          <>
            <ChatMessageList
              isLoading={isLoading}
              isStreaming={isStreaming}
              isReasoning={isReasoning}
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
