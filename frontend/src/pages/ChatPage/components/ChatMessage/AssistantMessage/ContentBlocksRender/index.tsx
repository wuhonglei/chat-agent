import { ContentBlock } from "@/interfaces/contentBlock";
import React from "react";
import { ReasoningBlockRender } from "./ReasoningBlockRender.tsx";
import { TextBlockRender } from "./TextBlockRender.tsx";
import { ToolBlockRender } from "./ToolBlockRender/index.tsx";
import { deriveRenderableBlocks } from "./viewModel.ts";

type Props = {
  contentBlocks: ContentBlock[];
  isStreaming: boolean;
};

const ContentBlocksRender: React.FC<Props> = ({ contentBlocks, isStreaming }) => {
  const renderableBlocks = deriveRenderableBlocks(contentBlocks, isStreaming);

  return (
    <div className="flex flex-col gap-2">
      {renderableBlocks.map(item => {
        if (item.type === "thinking") {
          return <ReasoningBlockRender key={item.key} contentBlock={item.block} status={item.status} />;
        }
        if (item.type === "text") {
          return <TextBlockRender key={item.key} contentBlock={item.block} status={item.status} />;
        }
        if (item.type === "tool_use") {
          return (
            <ToolBlockRender
              key={item.key}
              toolUseBlock={item.block}
              status={item.status}
              toolResultBlock={item.result}
            />
          );
        }
        return null;
      })}
    </div>
  );
};

export default React.memo(ContentBlocksRender);
