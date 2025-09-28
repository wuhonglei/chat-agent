import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useChatMessage } from "@/hooks";
import { useMemoizedFn } from "ahooks";
import { ChatInputFormValues, ChatMessage as ChatMessageType } from "@/types";
import { Card, Form } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import { SourceData } from "@/types";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";

const ChatPage: React.FC = () => {
  const { sendMessage, isStreaming, isLoading, isReasoning } = useChatMessage();
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

  const handleCloseSource = useMemoizedFn(() => {
    setSourceData(undefined);
  });

  return (
    <div className="flex h-full bg-white">
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
        {/* Messages */}
        <ChatMessageList
          isLoading={isLoading}
          isStreaming={isStreaming}
          isReasoning={isReasoning}
          onSourceClick={handleSourceClick}
          onEditMessage={handleEditMessage}
          className={styles["child-container"]}
        />
        {/* Input area */}
        <ChatInput
          form={form}
          onSend={sendMessage}
          isLoading={isLoading}
          isStreaming={isStreaming}
          className={styles["child-container"]}
        />
      </Card>
      {/* Sources panel */}
      <SourceSider sourceData={sourceData} onClose={handleCloseSource} />
    </div>
  );
};

export default React.memo(ChatPage);
