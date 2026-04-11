import { ImageBlock } from "@/interfaces/contentBlock";
import { fileAPI } from "@/services/file";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import type { UploadFile } from "antd";
import { GetProp, GetRef } from "antd";
import React from "react";

function withServerImagePreview(file: UploadFile<ImageBlock>): UploadFile<ImageBlock> {
  if (file.status !== "done" || file.response == null) {
    return file;
  }
  const { url } = file.response;
  if (typeof url !== "string" || !url) {
    return file;
  }
  // @ant-design/x 列表预览优先级为 thumbUrl || url || 本地 canvas 缩略图（约 200px，模糊）。
  // 上传完成后改为使用服务端地址，避免使用 base64 / 低分辨率预览。
  return { ...file, url, thumbUrl: url };
}

export interface ChatInputSenderHeaderProps {
  attachmentsRef: React.RefObject<GetRef<typeof Attachments> | null>;
  attachmentItems: GetProp<AttachmentsProps, "items">;
  setAttachmentItems: React.Dispatch<React.SetStateAction<GetProp<AttachmentsProps, "items">>>;
}

const ChatInputSenderHeader: React.FC<ChatInputSenderHeaderProps> = ({
  attachmentsRef,
  attachmentItems,
  setAttachmentItems,
}) => {
  const hasAttachmentItems = Boolean(attachmentItems?.length);

  return (
    <Sender.Header
      styles={{
        header: {
          display: "none",
        },
        content: {
          padding: 0,
        },
      }}
      style={{ border: "none" }}
      open
      closable={false}
      forceRender
    >
      <Attachments
        ref={attachmentsRef}
        accept="image/*"
        styles={{
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
        }}
        items={attachmentItems}
        placeholder={undefined}
        onChange={({ fileList }) =>
          setAttachmentItems(fileList.map(f => withServerImagePreview(f as UploadFile<ImageBlock>)))
        }
        customRequest={async options => {
          const { file, onError, onSuccess } = options;
          try {
            const block = await fileAPI.uploadChatImage(file as File);
            onSuccess?.(block);
          } catch (e) {
            onError?.(e as Error);
          }
        }}
        getDropContainer={() => document.body}
      />
    </Sender.Header>
  );
};

export default React.memo(ChatInputSenderHeader);
