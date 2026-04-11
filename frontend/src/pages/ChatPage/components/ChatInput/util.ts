import { ImageBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import { GetProp } from "antd";
import { ButtonState } from "./constant";

export function getAttachmentBlocks(items: GetProp<AttachmentsProps, "items"> | undefined): ImageBlock[] {
  if (!items?.length) {
    return [];
  }
  const out: ImageBlock[] = [];
  for (const item of items) {
    if (item.status !== "done" || item.response == null) {
      continue;
    }
    const r = item.response as unknown;
    if (typeof r === "object" && r !== null && "type" in r && (r as ImageBlock).type === "image") {
      out.push(r as ImageBlock);
    }
  }
  return out;
}

export function isButtonDisabled(buttonState: ButtonState) {
  return buttonState === ButtonState.WaitingType;
}

export function isStreamingState(buttonState: ButtonState) {
  return buttonState === ButtonState.Streaming;
}
