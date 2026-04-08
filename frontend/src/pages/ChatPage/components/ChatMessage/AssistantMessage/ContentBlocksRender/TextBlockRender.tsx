import { ContentBlockRenderStatus, TextBlock } from "@/interfaces/contentBlock";
import React from "react";
import MarkdownContainer from "../../../MarkdownContainer";

type Props = {
  contentBlock: TextBlock;
  status: ContentBlockRenderStatus;
};

export const TextBlockRender: React.FC<Props> = ({ contentBlock, status }) => {
  const isStreamingLike = status === ContentBlockRenderStatus.Start || status === ContentBlockRenderStatus.Streaming;
  return (
    <MarkdownContainer className={`text-base w-full ${isStreamingLike ? "opacity-95" : ""}`}>
      {contentBlock.text}
    </MarkdownContainer>
  );
};
