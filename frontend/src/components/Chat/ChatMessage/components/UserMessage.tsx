import React, { useState } from "react";
import { Button } from "antd";
import { Bubble, Sender } from "@ant-design/x";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { EditOutlined } from "@ant-design/icons";
import CopyButton from "@/components/common/CopyButton";
import { isInputEnter } from "@/utils";
import { trim } from "lodash-es";

interface UserMessageProps {
  message: ChatMessageType;
  onEditMessage: (content: string) => void;
}

const UserMessage: React.FC<UserMessageProps> = ({
  message,
  onEditMessage,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [messageContent, setMessageContent] = useState(message.content);
  function handleConfirm() {
    if (!messageContent) {
      return;
    }
    setIsEditing(false);
    onEditMessage(messageContent);
  }

  function handleSend(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (isInputEnter(event)) {
      event.preventDefault();
      handleConfirm();
    }
  }

  return (
    <section className="mt-3 w-full flex justify-end">
      <Bubble
        placement="end"
        variant={isEditing ? "borderless" : "filled"}
        className={isEditing ? "min-w-[80%]" : "max-w-[70%]"}
        content={message.content}
        classNames={{ content: "w-full whitespace-pre-wrap wrap-break-word" }}
        messageRender={(content: string) =>
          isEditing ? (
            <Sender
              actions={false}
              defaultValue={content}
              onKeyDown={handleSend}
              onChange={value => setMessageContent(trim(value))}
              footer={
                <div className="flex justify-end gap-2">
                  <Button
                    shape="round"
                    type="default"
                    onClick={() => setIsEditing(false)}
                  >
                    取消
                  </Button>
                  <Button
                    shape="round"
                    type="primary"
                    onClick={handleConfirm}
                    disabled={!messageContent}
                  >
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
            <div className="flex gap-2">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => setIsEditing(true)}
              />
              <CopyButton text={message.content} children={null} />
            </div>
          )
        }
      />
    </section>
  );
};

export default React.memo(UserMessage);
