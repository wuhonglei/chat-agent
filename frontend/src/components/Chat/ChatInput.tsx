import { Input, Space, Switch } from "antd";
import classNames from "classnames";
import React, { useState } from "react";

const { TextArea } = Input;

interface ChatInputProps {
  isLoading: boolean;
  isStreaming: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (message: string, useKnowledgeBase: boolean) => void;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
  isStreaming,
  className,
  style,
}) => {
  const [message, setMessage] = useState("");
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(true);

  const handleSend = () => {
    if (message.trim() && !isLoading && !isStreaming) {
      onSend(message, useKnowledgeBase);
      setMessage("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={classNames("p-4 bg-white", className)} style={style}>
      <div className="mb-2">
        <Space>
          <span className="text-gray-600">使用知识库：</span>
          <Switch
            checked={useKnowledgeBase}
            onChange={setUseKnowledgeBase}
            disabled={isLoading || isStreaming}
          />
        </Space>
      </div>
      <div className="flex gap-2">
        <TextArea
          value={message}
          onChange={e => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="输入您的问题..."
          autoSize={{ minRows: 2, maxRows: 4 }}
          disabled={isLoading || isStreaming}
          className="flex-1"
        />
      </div>
    </div>
  );
};

export default ChatInput;
