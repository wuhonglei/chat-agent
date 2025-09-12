import React, { useState, useRef, useEffect } from "react";
import { Card, Empty, Spin, Button } from "antd";
import { ClearOutlined } from "@ant-design/icons";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import ChatMessage from "../components/Chat/ChatMessage";
import ChatInput from "../components/Chat/ChatInput";
import SourceCard from "../components/Chat/SourceCard";
import {
  addMessage,
  clearMessages,
  setStreaming,
  appendToLastMessage,
  setSources,
} from "../store/slices/chatSlice";
import { chatAPI } from "../services/api";
import { ChatMessage as ChatMessageType, StreamMessage } from "../types";

const ChatPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming, sources, sessionId } =
    useAppSelector((state) => state.chat);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [streamController, setStreamController] =
    useState<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (
    message: string,
    useKnowledgeBase: boolean,
  ) => {
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

    try {
      // Start streaming
      const controller = await chatAPI.streamMessage(
        {
          message,
          session_id: sessionId || undefined,
          use_knowledge_base: useKnowledgeBase,
          history: messages.slice(-10), // Send last 10 messages as context
        },
        (data: StreamMessage) => {
          // Handle streaming data
          if (data.type === "content") {
            dispatch(appendToLastMessage(data.data));
          } else if (data.type === "sources") {
            dispatch(setSources(data.data));
          } else if (data.type === "done") {
            dispatch(setStreaming(false));
            setStreamController(null);
          }
        },
        (error: Error) => {
          console.error("Stream error:", error);
          dispatch(setStreaming(false));
          setStreamController(null);
        },
        () => {
          dispatch(setStreaming(false));
          setStreamController(null);
        },
      );
      setStreamController(controller);
    } catch (error) {
      console.error("Failed to send message:", error);
      dispatch(setStreaming(false));
    }
  };

  const handleClearChat = () => {
    if (streamController) {
      streamController.abort();
      setStreamController(null);
    }
    dispatch(clearMessages());
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="flex-1 overflow-hidden flex">
        {/* Chat area */}
        <div className="flex-1 flex flex-col">
          <Card
            className="m-4 mb-0 flex-1 overflow-hidden flex flex-col"
            styles={{
              body: {
                padding: 0,
                flex: 1,
                display: "flex",
                flexDirection: "column",
              },
            }}
          >
            {/* Header */}
            <div className="px-4 py-3 border-b flex justify-between items-center">
              <h2 className="text-lg font-medium">智能问答</h2>
              <Button
                icon={<ClearOutlined />}
                onClick={handleClearChat}
                disabled={isStreaming}
              >
                清空对话
              </Button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4">
              {messages.length === 0 ? (
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
                    />
                  ))}
                  {isLoading && (
                    <div className="text-center py-4">
                      <Spin tip="思考中..." />
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <ChatInput
              onSend={handleSendMessage}
              isLoading={isLoading}
              isStreaming={isStreaming}
            />
          </Card>
        </div>

        {/* Sources panel */}
        {sources.length > 0 && (
          <div className="w-96 p-4 pl-0">
            <Card
              title="参考来源"
              className="h-full overflow-y-auto"
              styles={{ body: { padding: "16px" } }}
            >
              <SourceCard sources={sources} />
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;
