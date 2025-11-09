// Stream types
export interface StreamMessage {
  type:
    | "ack"
    | "refresh_conversation"
    | "reasoning"
    | "content"
    | "sources"
    | "tool_call"
    | "title"
    | "done"
    | "error";
  data?: any;
}
