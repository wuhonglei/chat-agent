import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { isInputEnter } from "@/utils";
import { EditOutlined } from "@ant-design/icons";
import { Bubble, Sender } from "@ant-design/x";
import { Button } from "antd";
import classNames from "classnames";
import { trim } from "lodash-es";
import React, { useState } from "react";
import styles from "./css/UserMessage.module.css";

interface UserMessageProps {
  message: ChatMessageType;
  onEditMessage: (content: string) => void;
}

const UserMessage: React.FC<UserMessageProps> = ({ message, onEditMessage }) => {
  const [isEditing, setIsEditing] = useState(false);
  const textContent = getMessageTextFromBlocks(message.contentBlocks);
  const [messageContent, setMessageContent] = useState(textContent);
  function handleConfirm() {
    if (!messageContent) {
      return;
    }
    setIsEditing(false);
    onEditMessage(messageContent);
  }

  function handleKeyDown(event: React.KeyboardEvent<Element>) {
    if (isInputEnter(event)) {
      event.preventDefault();
      handleConfirm();
    }
  }

  return (
    <section className={classNames("mt-3 w-full flex justify-end", styles.container)}>
      <Bubble
        placement="end"
        content={textContent}
        variant={isEditing ? "borderless" : "filled"}
        className={isEditing ? "min-w-[80%]" : "max-w-[70%]"}
        classNames={{
          body: "w-full",
          content: "w-full whitespace-pre-wrap wrap-break-word",
        }}
        contentRender={(content: string) =>
          isEditing ? (
            <Sender
              suffix={false}
              defaultValue={content}
              onKeyDown={handleKeyDown}
              onChange={value => setMessageContent(trim(value))}
              footer={
                <div className="flex justify-end gap-2">
                  <Button shape="round" type="default" onClick={() => setIsEditing(false)}>
                    取消
                  </Button>
                  <Button shape="round" type="primary" onClick={handleConfirm} disabled={!messageContent}>
                    发送
                  </Button>
                </div>
              }
            />
          ) : (
            <>{content}</>
          )
        }
        footer={
          isEditing ? null : (
            <div className={classNames("flex gap-2", styles.operation)}>
              <Button size="small" type="text" icon={<EditOutlined />} onClick={() => setIsEditing(true)} />
              <CopyButton text={textContent} children={null} />
            </div>
          )
        }
      />
    </section>
  );
};

export default React.memo(UserMessage);
