// Stream types
export interface StreamMessage {
  type: "reasoning" | "content" | "sources" | "tool_call" | "done" | "error";
  data?: any;
}
