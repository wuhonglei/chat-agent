import React from "react";
import { Button, Card } from "antd";
import { ChatMessage as ChatMessageType } from "@/types";
import { EditOutlined } from "@ant-design/icons";
import CopyButton from "@/components/common/CopyButton";
import styles from "./css/UserMessage.module.css";
import classNames from "classnames";

interface UserMessageProps {
  message: ChatMessageType;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div
      className={classNames(
        "flex flex-col mt-3 items-end gap-2",
        styles.container
      )}
    >
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
      <div
        className={classNames(
          "h-6 w-full flex items-center justify-end gap-2 transition",
          styles.operation
        )}
      >
        <Button size="small" type="text" icon={<EditOutlined />} />
        <CopyButton text={message.content} children={null} />
      </div>
    </div>
  );
};

export default React.memo(UserMessage);
