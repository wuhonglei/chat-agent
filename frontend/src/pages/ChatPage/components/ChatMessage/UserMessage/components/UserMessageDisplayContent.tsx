import {
  ContentBlock,
  isUserAttachmentBlock,
  type TextBlock,
  type UserAttachmentBlock,
} from "@/interfaces/contentBlock";
import { FileCard, type FileCardProps } from "@ant-design/x";
import React, { useMemo } from "react";

function attachmentToFileCardItem(block: UserAttachmentBlock): FileCardProps {
  switch (block.type) {
    case "image": {
      const ext = block.mime.split("/")[1]?.split("+")[0] || "png";
      return {
        key: block.id,
        name: `image.${ext}`,
        byte: block.size,
        src: block.url,
        type: "image",
      };
    }
  }
}

function partitionUserBlocks(blocks: ContentBlock[]) {
  const attachments: UserAttachmentBlock[] = [];
  const texts: TextBlock[] = [];
  for (const block of blocks) {
    if (block.type === "text") {
      texts.push(block);
    } else if (isUserAttachmentBlock(block)) {
      attachments.push(block);
    }
  }
  return { attachments, texts };
}

export interface UserMessageDisplayContentProps {
  contentBlocks: ContentBlock[];
}

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({ contentBlocks }) => {
  const { attachments, texts } = useMemo(() => partitionUserBlocks(contentBlocks), [contentBlocks]);
  const fileCardItems = useMemo(() => attachments.map(attachmentToFileCardItem), [attachments]);

  return (
    <div className="flex w-full flex-col items-end gap-2" style={{ borderRadius: "inherit" }}>
      {fileCardItems.length > 0 ? (
        <div className="max-w-full">
          <FileCard.List items={fileCardItems} overflow="wrap" style={{ padding: 0 }} />
        </div>
      ) : null}
      {texts.length > 0 ? (
        <div
          className="whitespace-pre-wrap wrap-break-word"
          style={
            fileCardItems.length > 0
              ? {
                  padding: 12,
                  borderRadius: "inherit",
                  backgroundColor: "var(--ant-color-fill-content)",
                }
              : undefined
          }
        >
          {texts.map(block => (
            <span key={block.id}>{block.text}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default React.memo(UserMessageDisplayContent);
