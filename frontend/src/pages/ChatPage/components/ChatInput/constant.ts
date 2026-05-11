import type { NamePath } from "antd/es/form/interface";

/** 网站构建模式下强制关闭且不可勾选的 MCP（与 backend mcp_registry 前端 id 一致） */
export const websiteBuildModeForcedOffMcpIds = ["weather-mcp", "code-exec-mcp"] as const;

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
