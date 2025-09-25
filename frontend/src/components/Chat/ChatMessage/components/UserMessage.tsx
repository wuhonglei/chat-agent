import React from "react";
import { ChatMessage as ChatMessageType } from "@/types";
import { Card } from "antd";

interface UserMessageProps {
  message: ChatMessageType;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div className="flex flex-col mt-3 items-end gap-4">
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
      <div className="h-6">123</div>
    </div>
  );
};

export default React.memo(UserMessage);
