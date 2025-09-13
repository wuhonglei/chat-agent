import { ChatMessage as ChatMessageType } from "@/types";
import { Card } from "antd";
import React, { useEffect, useState } from "react";

interface UserMessageProps {
  message: ChatMessageType;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  const [displayContent, setDisplayContent] = useState("");

  useEffect(() => {
    setDisplayContent(message.content);
  }, [message.content]);

  return (
    <div className="flex mt-3 mb-10 justify-end">
      <Card
        className="max-w-[70%] animate-slide-up"
        styles={{
          body: {
            padding: "9px 16px",
            backgroundColor: "#F5F5F5",
            fontSize: "16px",
          },
        }}
      >
        {displayContent}
      </Card>
    </div>
  );
};

export default UserMessage;
