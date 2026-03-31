import { ContentBlock, getMessageTextFromBlocks, getMessageThinkingFromBlocks } from "@/interfaces/contentBlock";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import React from "react";

type Props = {
  contentBlocks: ContentBlock[];
};

const ContentBlocksRenderer: React.FC<Props> = ({ contentBlocks }) => {
  const thinking = getMessageThinkingFromBlocks(contentBlocks);
  const text = getMessageTextFromBlocks(contentBlocks);
  return (
    <div className="flex flex-col gap-2">
      {thinking ? <MarkdownContainer gray>{thinking}</MarkdownContainer> : null}
      <MarkdownContainer className="text-base w-full">{text}</MarkdownContainer>
    </div>
  );
};

export default React.memo(ContentBlocksRenderer);
