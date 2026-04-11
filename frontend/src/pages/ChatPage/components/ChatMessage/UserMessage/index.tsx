import { ChatMessage as ChatMessageType } from "@/interfaces";
import { getMessageTextFromBlocks, isUserMessageContentTextOnly } from "@/interfaces/contentBlock";
import { Bubble } from "@ant-design/x";
import classNames from "classnames";
import React, { useState } from "react";
import UserMessageDisplayContent from "./components/UserMessageDisplayContent";
import UserMessageEditContent from "./components/UserMessageEditContent";
import UserMessageFooter from "./components/UserMessageFooter";
import styles from "./UserMessage.module.css";

interface UserMessageProps {
  message: ChatMessageType;
  isLastMessage: boolean;
  onEditMessage: (content: string) => void;
  onDeleteMessage: () => void | Promise<void>;
}

const UserMessage: React.FC<UserMessageProps> = ({ message, isLastMessage, onEditMessage, onDeleteMessage }) => {
  const [isEditing, setIsEditing] = useState(false);
  const textContent = getMessageTextFromBlocks(message.contentBlocks);
  const canEdit = isUserMessageContentTextOnly(message.contentBlocks);
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
              onCancel={() => setIsEditing(false)}
              onConfirm={editedContent => {
                setIsEditing(false);
                onEditMessage(editedContent);
              }}
            />
          ) : (
            <UserMessageDisplayContent contentBlocks={message.contentBlocks} />
          )
        }
        footer={
          isEditing ? null : (
            <UserMessageFooter
              canEdit={canEdit}
              textContent={textContent}
              showDelete={isLastMessage}
              onDelete={onDeleteMessage}
              onEdit={() => setIsEditing(true)}
            />
          )
        }
      />
    </section>
  );
};

export default React.memo(UserMessage);
