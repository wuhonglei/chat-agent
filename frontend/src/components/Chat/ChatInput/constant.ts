import { NamePath } from "rc-field-form/es/interface";

export const names = {
  message: ["message"] as NamePath,
  thinkMode: ["thinkMode"] as NamePath,
  webSearch: ["sourceConfig", "webSearch"] as NamePath,
  confluence: ["sourceConfig", "confluence"] as NamePath,
  googleDocs: ["sourceConfig", "googleDocs"] as NamePath,
};

export enum ButtonState {
  WaitingType = "WaitingType",
  Typing = "Typing",
  Streaming = "Streaming",
}
