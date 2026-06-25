import { type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { AttachmentsProps } from "@ant-design/x";
import { GetProp, type UploadFile } from "antd";
import { ButtonState } from "../constant";

export const CHAT_ATTACHMENT_TOOLTIP = "支持图片、PDF、Excel、Markdown 及文本/代码文件，单文件不超过 10MB，最多 5 个附件";

export function withServerAttachmentPreview(file: UploadFile<UserAttachmentBlock>): UploadFile<UserAttachmentBlock> {
  if (file.status !== "done" || file.response == null) {
    return file;
  }
  const response = file.response;
  const { url } = response;
  if (typeof url !== "string" || !url) {
    return file;
  }
  // @ant-design/x 列表预览优先级为 thumbUrl || url || 本地 canvas 缩略图（约 200px，模糊）。
  return { ...file, url };
}

export function isImageAttachment(file: UploadFile<UserAttachmentBlock>): boolean {
  const response = file.response;
  if (typeof response === "object" && response !== null && "type" in response && response.type === "image") {
    return true;
  }
  const mimeType = (file.type || file.originFileObj?.type || "").toLowerCase();
  return mimeType.startsWith("image/");
}

export function sortAttachmentsByImageFirst(
  fileList: UploadFile<UserAttachmentBlock>[]
): UploadFile<UserAttachmentBlock>[] {
  const images: UploadFile<UserAttachmentBlock>[] = [];
  const others: UploadFile<UserAttachmentBlock>[] = [];
  for (const file of fileList) {
    if (isImageAttachment(file)) {
      images.push(file);
      continue;
    }
    others.push(file);
  }
  return [...images, ...others];
}

export function getChatInputAttachmentStyles(hasAttachmentItems: boolean): GetProp<AttachmentsProps, "styles"> {
  return {
    placeholder: {
      padding: 0,
      border: "none",
    },
    upload: {
      display: "none",
    },
    list: {
      padding: 0,
    },
    root: hasAttachmentItems
      ? {
          padding: 12,
          paddingBottom: 0,
        }
      : undefined,
  };
}

export function isButtonDisabled(buttonState: ButtonState) {
  return buttonState === ButtonState.WaitingType;
}
