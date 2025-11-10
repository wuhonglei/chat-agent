export enum SearchSourceType {
  WEB_SEARCH = "web_search",
  CONFLUENCE = "confluence",
}

export type RoleType = "user" | "assistant" | "system";

export enum MessageStatus {
  PENDING = "pending",
  STOPPED = "stopped",
  DONE = "done",
  FAILED = "failed",
}
