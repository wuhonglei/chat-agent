import type { NamePath } from "antd/es/form/interface";

export const names = {
  content: ["content"] as NamePath,
  thinkMode: ["thinkMode"] as NamePath,
  websiteBuildMode: ["websiteBuildMode"] as NamePath,
  mcpAutoMode: ["mcpAutoMode"] as NamePath,
  sourceConfig: ["sourceConfig"] as NamePath,
  modelId: ["modelID"] as NamePath,
};

export enum ButtonState {
  WaitingType = "WaitingType",
  Typing = "Typing",
  Streaming = "Streaming",
}
