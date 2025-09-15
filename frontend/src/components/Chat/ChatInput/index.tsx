import { Input, Switch } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import styles from "./index.module.css";

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
    if (message.trim()) {
      onSend(message.trim(), useKnowledgeBase);
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
    <div className={classNames("p-4 bg-white gap-2", className)} style={style}>
      <div
        className={classNames(
          "flex flex-col gap-2 p-3",
          styles["input-container"]
        )}
      >
        <TextArea
          value={message}
          placeholder="发消息"
          className={classNames(styles.input)}
          onKeyUp={handleKeyPress}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={e => setMessage(e.target.value)}
        />
        <div>
          <span className="text-gray-600">使用知识库：</span>
          <Switch checked={useKnowledgeBase} onChange={setUseKnowledgeBase} />
        </div>
      </div>
    </div>
  );
};

export default ChatInput;
