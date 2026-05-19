import type { NamePath } from "antd/es/form/interface";

export const names = {
  content: ["content"] as NamePath,
  thinkMode: ["thinkMode"] as NamePath,
  agentMode: ["agentMode"] as NamePath,
  modelId: ["modelID"] as NamePath,
};

export enum ButtonState {
  WaitingType = "WaitingType",
  Typing = "Typing",
  Streaming = "Streaming",
}
