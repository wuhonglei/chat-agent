import image404 from "@/assets/imgs/404_image.png";
import { useIsSmallScreen } from "@/hooks";
import {
  ContentBlock,
  isUserAttachmentBlock,
  type PreviewableBlock,
  type TextBlock,
  type UserAttachmentBlock,
} from "@/interfaces/contentBlock";
import { DownOutlined, UpOutlined } from "@ant-design/icons";
import { FileCard, type FileCardProps } from "@ant-design/x";
import { Button } from "antd";
import classNames from "classnames";
import React, { useLayoutEffect, useMemo, useRef, useState } from "react";
import styles from "./UserMessageDisplayContent.module.css";

const TEXT_MAX_HEIGHT = 400;

interface AttachmentToFileCardItemOptions {
  isSmallScreen: boolean;
  onPreviewBlock?: (block: PreviewableBlock) => void;
}

function attachmentToFileCardItem(
  block: UserAttachmentBlock,
  { onPreviewBlock }: AttachmentToFileCardItemOptions,
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
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    case "excel":
      return {
        key: block.id,
        name: block.name?.trim() || "spreadsheet.xlsx",
        byte: block.size,
        onClick: () => {
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    case "docx":
      return {
        key: block.id,
        name: block.name?.trim() || "document.docx",
        byte: block.size,
        onClick: () => {
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    case "pptx":
      return {
        key: block.id,
        name: block.name?.trim() || "presentation.pptx",
        byte: block.size,
        onClick: () => {
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    case "markdown":
      return {
        key: block.id,
        name: block.name?.trim() || "document.md",
        byte: block.size,
        onClick: () => {
          if (onPreviewBlock) {
            onPreviewBlock(block);
            return;
          }
          window.open(block.url, "_blank", "noopener,noreferrer");
        },
      };
    case "text_file":
      return {
        key: block.id,
        name: block.name?.trim() || "file.txt",
        byte: block.size,
        onClick: () => {
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

interface UserMessageTextProps {
  texts: TextBlock[];
  hasAttachments: boolean;
}

const UserMessageText: React.FC<UserMessageTextProps> = ({ texts, hasAttachments }) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  useLayoutEffect(() => {
    if (expanded) {
      return;
    }
    const el = contentRef.current;
    if (!el) {
      return;
    }

    const update = () => {
      setOverflowing(el.scrollHeight > el.clientHeight + 2);
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, [expanded, texts]);

  const showExpand = overflowing && !expanded;
  const showCollapse = expanded;

  return (
    <div
      className={styles.textRoot}
      style={
        hasAttachments
          ? {
              padding: 12,
              borderRadius: "inherit",
              backgroundColor: "var(--ant-color-fill-content)",
            }
          : undefined
      }
    >
      <div
        ref={contentRef}
        className={classNames("whitespace-pre-wrap wrap-break-word", showExpand && styles.clipped)}
        style={expanded ? undefined : { maxHeight: TEXT_MAX_HEIGHT, overflow: "hidden" }}
      >
        {texts.map((block) => (
          <span key={block.id}>{block.text}</span>
        ))}
      </div>
      {showExpand ? (
        <div className={styles.toggleBar}>
          <Button
            type="link"
            size="small"
            className={styles.toggleBtn}
            icon={<DownOutlined />}
            aria-expanded={false}
            aria-label="展开完整消息"
            onClick={() => setExpanded(true)}
          >
            展开
          </Button>
        </div>
      ) : null}
      {showCollapse ? (
        <div className={styles.toggleBar}>
          <Button
            type="link"
            size="small"
            className={styles.toggleBtn}
            icon={<UpOutlined />}
            aria-expanded
            aria-label="收起消息"
            onClick={() => setExpanded(false)}
          >
            收起
          </Button>
        </div>
      ) : null}
    </div>
  );
};

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({
  contentBlocks,
  onPreviewBlock,
}) => {
  const isSmallScreen = useIsSmallScreen();
  const { attachments, texts } = useMemo(() => partitionUserBlocks(contentBlocks), [contentBlocks]);
  const fileCardItems = useMemo(
    () =>
      attachments.map((block) =>
        attachmentToFileCardItem(block, {
          isSmallScreen,
          onPreviewBlock,
        }),
      ),
    [attachments, isSmallScreen, onPreviewBlock],
  );

  return (
    <div className="flex w-full flex-col items-end gap-2" style={{ borderRadius: "inherit" }}>
      {fileCardItems.length > 0 ? (
        <div className="max-w-full">
          <FileCard.List items={fileCardItems} overflow="wrap" style={{ padding: 0 }} />
        </div>
      ) : null}
      {texts.length > 0 ? (
        <UserMessageText
          key={texts.map((block) => `${block.id}:${block.text}`).join("\n")}
          texts={texts}
          hasAttachments={fileCardItems.length > 0}
        />
      ) : null}
    </div>
  );
};

export default React.memo(UserMessageDisplayContent);
