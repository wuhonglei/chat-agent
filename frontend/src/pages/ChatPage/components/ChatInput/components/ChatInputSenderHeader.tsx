import { type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { fileAPI } from "@/services/file";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import type { UploadFile } from "antd";
import { GetProp, GetRef, message } from "antd";
import React from "react";
import { CHAT_ATTACHMENT_ACCEPT, MAX_CHAT_ATTACHMENTS, getChatAttachmentValidationError } from "../util";
import { getChatInputAttachmentStyles, sortAttachmentsByImageFirst, withServerAttachmentPreview } from "./utils";

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
        styles={getChatInputAttachmentStyles(hasAttachmentItems)}
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
        onChange={({ fileList }) => {
          const normalizedFileList = fileList.map(f =>
            withServerAttachmentPreview(f as UploadFile<UserAttachmentBlock>)
          );
          setAttachmentItems(sortAttachmentsByImageFirst(normalizedFileList));
        }}
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
