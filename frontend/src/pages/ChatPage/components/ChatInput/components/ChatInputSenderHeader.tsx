import { type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { fileAPI } from "@/services/file";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import type { UploadFile } from "antd";
import { App, GetProp, GetRef } from "antd";
import React from "react";
import { CHAT_ATTACHMENT_ACCEPT, MAX_CHAT_ATTACHMENTS, getChatAttachmentValidationError, isImageFile } from "../util";
import { getChatInputAttachmentStyles, sortAttachmentsByImageFirst, withServerAttachmentPreview } from "./utils";

export interface ChatInputSenderHeaderProps {
  conversationId?: string;
  ensureConversationId?: () => Promise<string>;
  attachmentsRef: React.RefObject<GetRef<typeof Attachments> | null>;
  attachmentItems: GetProp<AttachmentsProps, "items">;
  setAttachmentItems: React.Dispatch<React.SetStateAction<GetProp<AttachmentsProps, "items">>>;
  canUploadImage: boolean;
}

const ChatInputSenderHeader: React.FC<ChatInputSenderHeaderProps> = ({
  conversationId,
  ensureConversationId,
  attachmentsRef,
  attachmentItems,
  setAttachmentItems,
  canUploadImage,
}) => {
  const { message } = App.useApp();
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
          if (!canUploadImage && isImageFile(file as File)) {
            message.warning("当前模型不支持图片，请切换支持图片的模型后再上传");
            return false;
          }
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
            const uploadConversationId = conversationId ?? (await ensureConversationId?.());
            if (!uploadConversationId) {
              throw new Error("缺少会话 ID，无法上传附件");
            }
            const block = await fileAPI.uploadChatAttachment(file as File, uploadConversationId);
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
