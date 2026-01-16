export enum SearchSourceType {
  WebSearch = "web_search",
  Confluence = "confluence",
}

export type RoleType = "user" | "assistant" | "system";

export enum MessageStatus {
  Pending = "pending",
  Stopped = "stopped",
  Done = "done",
  Failed = "failed",
}
