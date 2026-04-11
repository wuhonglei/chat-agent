import { ContentBlockRenderStatus } from "@/interfaces/contentBlock";

export const ACTIVE_STATUS_SET = new Set<ContentBlockRenderStatus>([
  ContentBlockRenderStatus.Start,
  ContentBlockRenderStatus.Streaming,
  ContentBlockRenderStatus.Running,
]);
