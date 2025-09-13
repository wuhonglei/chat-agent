import ChatInput from "@/components/Chat/ChatInput";
import ChatMessage from "@/components/Chat/ChatMessage";
import { chatAPI } from "@/services/api";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  appendToLastMessage,
  clearLastMessage,
  setLoading,
  setSources,
  setStreaming,
} from "@/store/slices/chatSlice";
import { ChatMessage as ChatMessageType, StreamMessage } from "@/types";
import { Card, Empty } from "antd";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import React, { useEffect, useRef } from "react";
import styles from "./index.module.css";

const ChatPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming, sessionId } = useAppSelector(
    state => state.chat
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    // messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (
    message: string,
    useKnowledgeBase: boolean
  ) => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      dispatch(clearLastMessage());
    }

    // Add user message
    const userMessage: ChatMessageType = {
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };
    dispatch(addMessage(userMessage));

    // Add empty assistant message for streaming
    const assistantMessage: ChatMessageType = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };
    dispatch(addMessage(assistantMessage));
    dispatch(setStreaming(true));
    dispatch(setLoading(true));

    try {
      abortControllerRef.current = new AbortController();

      // Start streaming
      await chatAPI.streamMessage(
        {
          message,
          session_id: sessionId || undefined,
          use_knowledge_base: useKnowledgeBase,
          history: messages.slice(-10), // Send last 10 messages as context
        },
        (data: StreamMessage) => {
          // Handle streaming data
          if (data.type === "content") {
            // 回答内容
            dispatch(appendToLastMessage(data.data));
            dispatch(setLoading(false));
          } else if (data.type === "sources") {
            // 知识库搜索结果
            dispatch(setSources(data.data));
          } else if (data.type === "done") {
            // 流结束
            dispatch(setStreaming(false));
            dispatch(setLoading(false));
          }
        },
        (error: Error) => {
          // 流错误
          console.error("Stream error:", error);
          dispatch(setStreaming(false));
        },
        () => {
          // 流结束
          dispatch(setStreaming(false));
        },
        abortControllerRef.current!
      );
    } catch (error) {
      console.error("Failed to send message:", error);
      dispatch(setStreaming(false));
    }
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Chat area */}
      <Card
        className="m-4 mb-0 flex-1 overflow-hidden flex flex-col"
        classNames={{
          body: classNames("flex flex-col h-full", styles.container),
        }}
        style={{
          border: "none",
        }}
      >
        {/* Messages */}
        <div
          className={classNames(
            "flex-1 overflow-y-auto px-2",
            styles["child-container"]
          )}
        >
          {isEmpty(messages) ? (
            <Empty description="开始提问吧" className="mt-20" />
          ) : (
            <>
              {messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  message={message}
                  isStreaming={
                    isStreaming &&
                    index === messages.length - 1 &&
                    message.role === "assistant"
                  }
                  isLoading={
                    isLoading &&
                    index === messages.length - 1 &&
                    message.role === "assistant"
                  }
                  onSourceClick={() => {}}
                />
              ))}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          isLoading={isLoading}
          isStreaming={isStreaming}
          onSend={handleSendMessage}
          className={styles["child-container"]}
        />
      </Card>
      {/* Sources panel */}
      {/* {sources.length > 0 && (
        <div className="w-96 p-4 pl-0">
          <Card
            title="参考来源"
            className="h-full overflow-y-auto"
            styles={{ body: { padding: "16px" } }}
          >
            <SourceCard sources={sources} />
          </Card>
        </div>
      )} */}
    </div>
  );
};

export default ChatPage;
