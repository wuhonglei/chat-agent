// Stream types
export interface StreamMessage {
  type:
    | "reasoning"
    | "content"
    | "sources"
    | "tool_call"
    | "title"
    | "done"
    | "error";
  data?: any;
}
