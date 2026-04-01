import {
  ContentBlock,
  ContentBlockRenderStatus,
  TextBlock,
  ThinkingBlock,
  ToolResultBlock,
  ToolUseBlock,
} from "@/interfaces/contentBlock";

const START_TEXT_LENGTH_THRESHOLD = 24;

export type RenderableContentBlock =
  | {
      key: string;
      type: "thinking";
      block: ThinkingBlock;
      status: ContentBlockRenderStatus;
    }
  | {
      key: string;
      type: "text";
      block: TextBlock;
      status: ContentBlockRenderStatus;
    }
  | {
      key: string;
      type: "tool_use";
      block: ToolUseBlock;
      status: ContentBlockRenderStatus;
      result?: ToolResultBlock;
    };

function isRenderableBlock(block: ContentBlock): block is TextBlock | ThinkingBlock | ToolUseBlock {
  return block.type !== "tool_result";
}

function getTextLikeStatus(
  text: string,
  isOpenBlock: boolean,
  doneStatus: ContentBlockRenderStatus
): ContentBlockRenderStatus {
  if (!isOpenBlock) {
    return doneStatus;
  }
  return text.length <= START_TEXT_LENGTH_THRESHOLD
    ? ContentBlockRenderStatus.Start
    : ContentBlockRenderStatus.Streaming;
}

function buildToolResultMaps(blocks: ContentBlock[]): {
  byToolUseId: Map<string, ToolResultBlock>;
  byToolCallId: Map<string, ToolResultBlock>;
} {
  const byToolUseId = new Map<string, ToolResultBlock>();
  const byToolCallId = new Map<string, ToolResultBlock>();
  for (const block of blocks) {
    if (block.type !== "tool_result") {
      continue;
    }
    byToolUseId.set(block.toolUseId, block);
    byToolCallId.set(block.toolCallId, block);
  }
  return { byToolUseId, byToolCallId };
}

export function deriveRenderableBlocks(
  blocks: ContentBlock[] | undefined,
  isStreaming: boolean
): RenderableContentBlock[] {
  const sourceBlocks = blocks || [];
  const { byToolUseId, byToolCallId } = buildToolResultMaps(sourceBlocks);
  const renderableIndexes = sourceBlocks
    .map((block, index) => ({ block, index }))
    .filter(({ block }) => isRenderableBlock(block))
    .map(({ index }) => index);
  const lastRenderableIndex = renderableIndexes.at(-1) ?? -1;
  const renderableIndexSet = new Set(renderableIndexes);

  const getHasNextRenderable = (index: number): boolean => {
    for (let i = index + 1; i < sourceBlocks.length; i += 1) {
      if (renderableIndexSet.has(i)) {
        return true;
      }
    }
    return false;
  };

  const items: RenderableContentBlock[] = [];
  for (let index = 0; index < sourceBlocks.length; index += 1) {
    const block = sourceBlocks[index];
    if (!isRenderableBlock(block)) {
      continue;
    }

    const isOpenBlock = isStreaming && index === lastRenderableIndex;
    const hasNextRenderable = getHasNextRenderable(index);

    if (block.type === "thinking") {
      items.push({
        key: block.id,
        type: "thinking",
        block,
        status: getTextLikeStatus(block.text, isOpenBlock && !hasNextRenderable, ContentBlockRenderStatus.Done),
      });
      continue;
    }

    if (block.type === "text") {
      items.push({
        key: block.id,
        type: "text",
        block,
        status: getTextLikeStatus(
          block.text,
          isOpenBlock && !hasNextRenderable,
          ContentBlockRenderStatus.StreamFinished
        ),
      });
      continue;
    }

    const result = byToolUseId.get(block.id) || (block.toolCallId ? byToolCallId.get(block.toolCallId) : undefined);
    let status: ContentBlockRenderStatus;
    if (result) {
      status = result.isError ? ContentBlockRenderStatus.Error : ContentBlockRenderStatus.Success;
    } else if (hasNextRenderable || !isStreaming) {
      status = ContentBlockRenderStatus.Done;
    } else if (block.argumentsJson !== undefined) {
      status = ContentBlockRenderStatus.Running;
    } else if (!block.argumentsText) {
      status = ContentBlockRenderStatus.Start;
    } else {
      status = ContentBlockRenderStatus.Streaming;
    }

    items.push({
      key: block.id,
      type: "tool_use",
      block,
      status,
      result,
    });
  }

  return items;
}
