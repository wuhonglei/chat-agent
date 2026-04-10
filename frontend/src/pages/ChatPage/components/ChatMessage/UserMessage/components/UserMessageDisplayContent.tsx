import { ContentBlock } from "@/interfaces/contentBlock";
import React from "react";

function renderUserBlocks(blocks: ContentBlock[]) {
  return blocks.map(block => {
    if (block.type === "text") {
      return (
        <span key={block.id} className="whitespace-pre-wrap wrap-break-word">
          {block.text}
        </span>
      );
    }
    if (block.type === "image") {
      return <img key={block.id} src={block.url} alt="" className="max-w-full max-h-80 rounded-md object-contain" />;
    }
    return null;
  });
}

export interface UserMessageDisplayContentProps {
  contentBlocks: ContentBlock[];
}

const UserMessageDisplayContent: React.FC<UserMessageDisplayContentProps> = ({ contentBlocks }) => (
  <div className="flex flex-col gap-2 items-end">{renderUserBlocks(contentBlocks)}</div>
);

export default React.memo(UserMessageDisplayContent);
