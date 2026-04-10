import { ChatMessage as ChatMessageType } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { isInputEnter } from "@/utils";
import { Bubble } from "@ant-design/x";
import classNames from "classnames";
import { trim } from "lodash-es";
import React, { useState } from "react";
import UserMessageDisplayContent from "./components/UserMessageDisplayContent";
import UserMessageEditContent from "./components/UserMessageEditContent";
import UserMessageFooter from "./components/UserMessageFooter";
import styles from "./UserMessage.module.css";

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
        content={textContent || " "}
        variant={isEditing ? "borderless" : "filled"}
        className={isEditing ? "min-w-[80%]" : "max-w-[70%]"}
        classNames={{
          body: "w-full",
          content: "w-full whitespace-pre-wrap wrap-break-word",
        }}
        contentRender={(content: string) =>
          isEditing ? (
            <UserMessageEditContent
              defaultValue={content}
              messageContent={messageContent}
              onChange={value => setMessageContent(trim(value))}
              onKeyDown={handleKeyDown}
              onCancel={() => setIsEditing(false)}
              onConfirm={handleConfirm}
            />
          ) : (
            <UserMessageDisplayContent contentBlocks={message.contentBlocks} />
          )
        }
        footer={isEditing ? null : <UserMessageFooter textContent={textContent} onEdit={() => setIsEditing(true)} />}
      />
    </section>
  );
};

export default React.memo(UserMessage);
