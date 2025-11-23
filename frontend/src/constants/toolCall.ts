export enum ToolCallStatus {
  Start = "start",
  CallingTool = "loading",
  ToolResultSuccess = "success",
  ToolResultError = "error",
  AllFinished = "allFinished",
}

export const timelineColorByStatus = {
  [ToolCallStatus.Start]: "gray", // 未完成/初始状态
  [ToolCallStatus.CallingTool]: "gray", // 开始调用某个 tool
  [ToolCallStatus.ToolResultSuccess]: "green", // 调用成功
  [ToolCallStatus.ToolResultError]: "red", // 调用失败
  [ToolCallStatus.AllFinished]: "green", // 调用结束
};
