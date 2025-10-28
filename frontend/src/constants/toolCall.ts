export enum ToolCallStatus {
  Start = "start",
  CallingTool = "callingTool",
  ToolResultSuccess = "toolResultSuccess",
  ToolResultError = "toolResultError",
  AllFinished = "allFinished",
}

export const timelineColorByStatus = {
  [ToolCallStatus.Start]: "gray", // 未完成/初始状态
  [ToolCallStatus.CallingTool]: "gray", // 开始调用某个 tool
  [ToolCallStatus.ToolResultSuccess]: "green", // 调用成功
  [ToolCallStatus.ToolResultError]: "red", // 调用失败
  [ToolCallStatus.AllFinished]: "green", // 调用结束
};
