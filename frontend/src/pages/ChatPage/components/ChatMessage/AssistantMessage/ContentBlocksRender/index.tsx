import { ContentBlock } from "@/interfaces/contentBlock";
import { Collapse } from "antd";
import React from "react";
import ProjectPreviewBlockRender from "./ProjectPreviewBlockRender.tsx";
import { ReasoningBlockRender } from "./ReasoningBlockRender.tsx";
import { TextBlockRender } from "./TextBlockRender.tsx";
import { ToolBlockRender } from "./ToolBlockRender/index.tsx";
import { deriveRenderableBlocks, RenderableContentBlock } from "./viewModel.ts";

type Props = {
  contentBlocks: ContentBlock[];
  isStreaming: boolean;
};

const ContentBlocksRender: React.FC<Props> = ({ contentBlocks, isStreaming }) => {
  const renderableBlocks = deriveRenderableBlocks(contentBlocks, isStreaming);
  let lastTextBlockIndex = -1;
  for (let index = renderableBlocks.length - 1; index >= 0; index -= 1) {
    if (renderableBlocks[index].type === "text") {
      lastTextBlockIndex = index;
      break;
    }
  }

  const renderBlock = (item: RenderableContentBlock) => {
    if (item.type === "thinking") {
      return <ReasoningBlockRender key={item.key} contentBlock={item.block} status={item.status} />;
    }
    if (item.type === "text") {
      return <TextBlockRender key={item.key} contentBlock={item.block} status={item.status} />;
    }
    if (item.type === "tool_use") {
      return (
        <ToolBlockRender key={item.key} status={item.status} toolUseBlock={item.block} toolResultBlock={item.result} />
      );
    }
    if (item.type === "project_preview") {
      return <ProjectPreviewBlockRender key={item.key} />;
    }
    return null;
  };

  const shouldUseFinishedLayout = !isStreaming && lastTextBlockIndex >= 0;
  const collapsedBlocks = shouldUseFinishedLayout ? renderableBlocks.slice(0, lastTextBlockIndex) : [];
  const tailBlocks = shouldUseFinishedLayout ? renderableBlocks.slice(lastTextBlockIndex) : [];

  return (
    <div className="flex flex-col gap-2">
      {!shouldUseFinishedLayout && renderableBlocks.map(renderBlock)}
      {shouldUseFinishedLayout && collapsedBlocks.length > 0 && (
        <Collapse
          items={[
            {
              key: "collapsed-process-blocks",
              label: "查看过程",
              children: <div className="flex flex-col gap-2">{collapsedBlocks.map(renderBlock)}</div>,
            },
          ]}
          className="bg-transparent"
        />
      )}
      {shouldUseFinishedLayout && tailBlocks.map(renderBlock)}
    </div>
  );
};

export default React.memo(ContentBlocksRender);
