import ChatInput from "@/components/Chat/ChatInput";
import { ChatMessageList } from "@/components/Chat/ChatMessage";
import { useAppSelector } from "@/store/hooks";
import { useChatMessage } from "@/hooks";
import { ChatMessage as ChatMessageType } from "@/types";
import { Card } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import { SourceData } from "@/types";
import styles from "./index.module.css";
import SourceSider from "@/components/Chat/SourceSider";

const ChatPage: React.FC = () => {
  const { messages } = useAppSelector(state => state.chat);
  const { sendMessage, isStreaming, isLoading, isReasoning } = useChatMessage();
  const [sourceData, setSourceData] = useState<SourceData | undefined>();

  function handleSourceClick(index: number, message: ChatMessageType) {
    if (sourceData?.index === index) {
      setSourceData(undefined);
    } else {
      setSourceData({ index, sources: message.sources || [] });
    }
  }

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
          messages={messages}
          isLoading={isLoading}
          isStreaming={isStreaming}
          isReasoning={isReasoning}
          onSourceClick={handleSourceClick}
          className={styles["child-container"]}
        />
        {/* Input area */}
        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading}
          isStreaming={isStreaming}
          className={styles["child-container"]}
        />
      </Card>
      {/* Sources panel */}
      <SourceSider
        sourceData={sourceData}
        onClose={() => setSourceData(undefined)}
      />
    </div>
  );
};

export default ChatPage;
