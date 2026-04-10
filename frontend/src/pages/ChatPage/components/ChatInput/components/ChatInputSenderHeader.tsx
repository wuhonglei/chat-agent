import { fileAPI } from "@/services/file";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import { GetProp, GetRef } from "antd";
import React from "react";

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
              }
            : undefined,
        }}
        items={attachmentItems}
        placeholder={undefined}
        onChange={({ fileList }) => setAttachmentItems(fileList)}
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
