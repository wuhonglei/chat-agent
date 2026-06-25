import { ContentBlock } from "@/interfaces/contentBlock";
import { Collapse } from "antd";
import React from "react";
import { useLastTextBlockIndex } from "./hooks.ts";
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
  const lastTextBlockIndex = useLastTextBlockIndex(renderableBlocks);

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
      return <ProjectPreviewBlockRender key={item.key} filepaths={item.filepaths} />;
    }
    return null;
  };

  // 非流式且文本后仍有过程块时，显示“查看过程”折叠区
  const shouldShowCollapsedProcessLayout =
    !isStreaming && lastTextBlockIndex >= 0 && lastTextBlockIndex !== renderableBlocks.length - 1;
  const collapsedBlocks = shouldShowCollapsedProcessLayout ? renderableBlocks.slice(0, lastTextBlockIndex) : [];
  const tailBlocks = shouldShowCollapsedProcessLayout ? renderableBlocks.slice(lastTextBlockIndex) : [];

  return (
    <div className="flex flex-col gap-2">
      {!shouldShowCollapsedProcessLayout && renderableBlocks.map(renderBlock)}
      {shouldShowCollapsedProcessLayout && collapsedBlocks.length > 0 && (
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
      {shouldShowCollapsedProcessLayout && tailBlocks.map(renderBlock)}
    </div>
  );
};

export default React.memo(ContentBlocksRender);
