import React from "react";

type Props = {
  isCallingTools: boolean;
  totalDuration: number | undefined;
};

const ToolCallTitle: React.FC<Props> = ({ isCallingTools, totalDuration }) => {
  if (isCallingTools) {
    return <>工具调用中</>;
  }
  if (!totalDuration) {
    return <>已完成工具调用</>;
  }

  return (
    <>
      已完成工具调用
      <span className="ml-1 text-black-tertiary">{totalDuration}s</span>
    </>
  );
};

export default React.memo(ToolCallTitle);
