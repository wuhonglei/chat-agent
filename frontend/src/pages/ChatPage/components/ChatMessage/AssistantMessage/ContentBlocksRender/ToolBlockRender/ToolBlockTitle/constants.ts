import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";

export const STATUS_TITLE_MAP: Record<ContentBlockRenderStatus, string> = {
  [ContentBlockRenderStatus.Start]: "工具准备中",
  [ContentBlockRenderStatus.Streaming]: "工具参数组装中",
  [ContentBlockRenderStatus.StreamFinished]: "工具参数已完成",
  [ContentBlockRenderStatus.Running]: "工具调用中",
  [ContentBlockRenderStatus.Success]: "工具调用成功",
  [ContentBlockRenderStatus.Error]: "工具调用失败",
  [ContentBlockRenderStatus.Done]: "工具调用结束",
};
