import { ChatMessage as ChatMessageType } from "@/types";
import { Card } from "antd";
import React from "react";

interface UserMessageProps {
  message: ChatMessageType;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div className="flex mt-3 mb-10 justify-end">
      <Card
        className="max-w-[70%] animate-slide-up"
        styles={{
          body: {
            fontSize: "16px",
            padding: "9px 16px",
            backgroundColor: "#F5F5F5",
          },
        }}
      >
        {message.content}
      </Card>
    </div>
  );
};

export default React.memo(UserMessage);
