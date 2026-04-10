import { ContentBlock, ImageBlock, TextBlock } from "@/interfaces/contentBlock";
import { FileCard, type FileCardProps } from "@ant-design/x";
import React, { useMemo } from "react";

function imageItemFromBlock(block: ImageBlock): FileCardProps {
  const ext = block.mime.split("/")[1]?.split("+")[0] || "png";
  return {
    key: block.id,
    name: `image.${ext}`,
    byte: block.size,
    src: block.url,
    type: "image",
  };
}

function partitionUserBlocks(blocks: ContentBlock[]) {
  const images: ImageBlock[] = [];
  const texts: TextBlock[] = [];
  for (const block of blocks) {
    if (block.type === "image") {
      images.push(block);
    } else if (block.type === "text") {
      texts.push(block);
    }
  }
  return { images, texts };
}

export interface UserMessageDisplayContentProps {
  contentBlocks: ContentBlock[];
}

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({ contentBlocks }) => {
  const { images, texts } = useMemo(() => partitionUserBlocks(contentBlocks), [contentBlocks]);
  const fileCardItems = useMemo(() => images.map(imageItemFromBlock), [images]);

  return (
    <div className="flex w-full flex-col items-end gap-2">
      {fileCardItems.length > 0 ? (
        <div className="max-w-full">
          <FileCard.List items={fileCardItems} overflow="wrap" style={{ padding: 0 }} />
        </div>
      ) : null}
      {texts.length > 0 ? (
        <div className="whitespace-pre-wrap wrap-break-word text-end">
          {texts.map(block => (
            <span key={block.id}>{block.text}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default React.memo(UserMessageDisplayContent);
