import React, { useState } from "react";
import { Button, Card, Input } from "antd";
import { ChatMessage as ChatMessageType } from "@/types";
import { EditOutlined } from "@ant-design/icons";
import CopyButton from "@/components/common/CopyButton";
import styles from "./css/UserMessage.module.css";
import classNames from "classnames";
import { isInputEnter } from "@/utils";

interface UserMessageProps {
  message: ChatMessageType;
  onEditMessage: (content: string) => void;
}

const { TextArea } = Input;

const UserMessage: React.FC<UserMessageProps> = ({
  message,
  onEditMessage,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [messageContent, setMessageContent] = useState(message.content);
  function handleConfirm() {
    setIsEditing(false);
    onEditMessage(messageContent);
  }

  function handleSend(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (isInputEnter(event)) {
      handleConfirm();
      event.preventDefault();
    }
  }

  return (
    <div
      className={classNames(
        "flex flex-col mt-3 items-end gap-2",
        styles.container
      )}
    >
      {isEditing ? (
        <div className="min-w-[70%]">
          <TextArea
            autoFocus
            onPressEnter={handleSend}
            defaultValue={messageContent}
            onChange={e => setMessageContent(e.target.value)}
          />
        </div>
      ) : (
        <Card
          className="max-w-[70%] animate-slide-up"
          styles={{
            body: {
              fontSize: "16px",
              padding: "9px 16px",
              whiteSpace: "pre-wrap",
              backgroundColor: "#F5F5F5",
            },
          }}
        >
          {message.content}
        </Card>
      )}
      <div
        className={classNames(
          "h-6 w-full flex items-center justify-end gap-2 transition",
          !isEditing && styles.operation
        )}
      >
        {isEditing ? (
          <>
            <Button
              size="small"
              type="default"
              onClick={() => setIsEditing(false)}
            >
              取消
            </Button>
            <Button size="small" type="primary" onClick={handleConfirm}>
              发送
            </Button>
          </>
        ) : (
          <>
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              onClick={() => setIsEditing(true)}
            />
            <CopyButton text={message.content} children={null} />
          </>
        )}
      </div>
    </div>
  );
};

export default React.memo(UserMessage);
