import image404 from "@/assets/imgs/404_image.png";
import { useIsSmallScreen } from "@/hooks";
import {
  ContentBlock,
  isUserAttachmentBlock,
  type PdfBlock,
  type PreviewableBlock,
  type TextBlock,
  type UserAttachmentBlock,
} from "@/interfaces/contentBlock";
import { downloadFileByUrl } from "@/utils";
import { FileCard, type FileCardProps } from "@ant-design/x";
import React, { useMemo } from "react";

function triggerPdfDownload(block: PdfBlock) {
  downloadFileByUrl(block.url, block.name?.trim() || "document.pdf");
}

interface AttachmentToFileCardItemOptions {
  isSmallScreen: boolean;
  onPreviewBlock?: (block: PreviewableBlock) => void;
}

function attachmentToFileCardItem(
  block: UserAttachmentBlock,
  { isSmallScreen, onPreviewBlock }: AttachmentToFileCardItemOptions
): FileCardProps {
  switch (block.type) {
    case "image": {
      const ext = block.mime.split("/")[1]?.split("+")[0] || "png";
      return {
        key: block.id,
        name: block.name?.trim() || `image.${ext}`,
        byte: block.size,
        src: block.url,
        type: "image",
        imageProps: {
          fallback: image404,
          styles: {
            root: {
              display: "flex",
              alignItems: "center",
            },
          },
        },
      };
    }
    case "pdf":
      return {
        key: block.id,
        name: block.name?.trim() || "document.pdf",
        byte: block.size,
        onClick: () => {
          // if (isSmallScreen) {
          //   triggerPdfDownload(block);
          //   return;
          // }
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    default: {
      const _exhaustiveCheck: never = block;
      return _exhaustiveCheck;
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
  onPreviewBlock?: (block: PreviewableBlock) => void;
}

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({ contentBlocks, onPreviewBlock }) => {
  const isSmallScreen = useIsSmallScreen();
  const { attachments, texts } = useMemo(() => partitionUserBlocks(contentBlocks), [contentBlocks]);
  const fileCardItems = useMemo(
    () =>
      attachments.map(block =>
        attachmentToFileCardItem(block, {
          isSmallScreen,
          onPreviewBlock,
        })
      ),
    [attachments, isSmallScreen, onPreviewBlock]
  );

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
