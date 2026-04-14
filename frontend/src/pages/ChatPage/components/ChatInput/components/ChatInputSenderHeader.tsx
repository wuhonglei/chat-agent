import { type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { fileAPI } from "@/services/file";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import type { UploadFile } from "antd";
import { GetProp, GetRef, message } from "antd";
import React from "react";
import { CHAT_ATTACHMENT_ACCEPT, MAX_CHAT_ATTACHMENTS, getChatAttachmentValidationError } from "../util";

function withServerAttachmentPreview(file: UploadFile<UserAttachmentBlock>): UploadFile<UserAttachmentBlock> {
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
        accept={CHAT_ATTACHMENT_ACCEPT}
        maxCount={MAX_CHAT_ATTACHMENTS}
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
        beforeUpload={file => {
          const error = getChatAttachmentValidationError(file as File, attachmentItems?.length ?? 0);
          if (error) {
            message.warning(error);
            return false;
          }
          return true;
        }}
        onChange={({ fileList }) =>
          setAttachmentItems(fileList.map(f => withServerAttachmentPreview(f as UploadFile<UserAttachmentBlock>)))
        }
        customRequest={async options => {
          const { file, onError, onSuccess } = options;
          try {
            const block = await fileAPI.uploadChatAttachment(file as File);
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
