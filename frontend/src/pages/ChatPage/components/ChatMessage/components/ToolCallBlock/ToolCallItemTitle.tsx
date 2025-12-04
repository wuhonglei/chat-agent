import { TimelineMessage } from "@/interfaces";
import { Tag } from "antd";
import React from "react";

type Props = {
  index: number;
  message: TimelineMessage;
};

const ToolCallItemTitle: React.FC<Props> = ({ index, message }) => {
  return (
    <div className="flex items-center gap-2">
      <span className="text-black-secondary">calling tool {index + 1}</span>
      <Tag color="processing" variant="filled" style={{ marginRight: 0 }}>
        {message.toolCall.function.name}
      </Tag>
      {"duration" in message && message.duration && (
        <span className="text-black-tertiary">{message.duration}s</span>
      )}
    </div>
  );
};

export default React.memo(ToolCallItemTitle);
