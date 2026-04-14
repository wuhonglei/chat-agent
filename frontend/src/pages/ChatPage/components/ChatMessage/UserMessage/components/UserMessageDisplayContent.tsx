import { useIsSmallScreen } from "@/hooks";
import {
  ContentBlock,
  PdfBlock,
  isUserAttachmentBlock,
  type TextBlock,
  type UserAttachmentBlock,
} from "@/interfaces/contentBlock";
import { FileCard, type FileCardProps } from "@ant-design/x";
import React, { useMemo } from "react";

function triggerPdfDownload(block: PdfBlock) {
  const anchor = document.createElement("a");
  anchor.href = block.url;
  anchor.download = block.name?.trim() || "document.pdf";
  anchor.rel = "noopener noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
}

interface AttachmentToFileCardItemOptions {
  isSmallScreen: boolean;
  onPreviewPdf?: (block: PdfBlock) => void;
}

function attachmentToFileCardItem(
  block: UserAttachmentBlock,
  { isSmallScreen, onPreviewPdf }: AttachmentToFileCardItemOptions
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
          if (isSmallScreen) {
            triggerPdfDownload(block);
            return;
          }
          if (onPreviewPdf) {
            onPreviewPdf(block);
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
  onPreviewPdf?: (block: PdfBlock) => void;
}

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({ contentBlocks, onPreviewPdf }) => {
  const isSmallScreen = useIsSmallScreen();
  const { attachments, texts } = useMemo(() => partitionUserBlocks(contentBlocks), [contentBlocks]);
  const fileCardItems = useMemo(
    () =>
      attachments.map(block =>
        attachmentToFileCardItem(block, {
          isSmallScreen,
          onPreviewPdf,
        })
      ),
    [attachments, isSmallScreen, onPreviewPdf]
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
