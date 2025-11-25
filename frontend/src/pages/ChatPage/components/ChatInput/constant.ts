import type { NamePath } from "antd/es/form/interface";

export const names = {
  content: ["content"] as NamePath,
  thinkMode: ["thinkMode"] as NamePath,
  mcpAutoMode: ["mcpAutoMode"] as NamePath,
  sourceConfig: ["sourceConfig"] as NamePath,
};

export enum ButtonState {
  WaitingType = "WaitingType",
  Typing = "Typing",
  Streaming = "Streaming",
}
