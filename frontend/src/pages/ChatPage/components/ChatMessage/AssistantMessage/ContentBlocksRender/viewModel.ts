import {
  ContentBlock,
  ContentBlockRenderStatus,
  TextBlock,
  ThinkingBlock,
  ToolResultBlock,
  ToolUseBlock,
} from "@/interfaces/contentBlock";
import { displayMcpToolName } from "@/utils/toolNaming";
import { isEmpty } from 'lodash-es';

const START_TEXT_LENGTH_THRESHOLD = 24;
const PROJECT_PREVIEW_TOOLS = new Set(["present_files"]);

function toolBlockMatchesPreview(block: ToolUseBlock): boolean {
  return PROJECT_PREVIEW_TOOLS.has(displayMcpToolName(block));
}

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
    }
  | {
      key: string;
      type: "project_preview";
      filepaths: string[];
    };

function isRenderableBlock(block: ContentBlock): block is TextBlock | ThinkingBlock | ToolUseBlock {
  return block.type !== "tool_result" && block.type !== "image";
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

interface ToolResultMaps {
  byToolUseId: Map<string, ToolResultBlock>;
  byToolCallId: Map<string, ToolResultBlock>;
}

function buildToolResultMaps(blocks: ContentBlock[]): ToolResultMaps {
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

function findToolResult(block: ToolUseBlock, maps: ToolResultMaps): ToolResultBlock | undefined {
  return maps.byToolUseId.get(block.id) ?? (block.toolCallId ? maps.byToolCallId.get(block.toolCallId) : undefined);
}

function isSuccessfulPreviewTool(block: ToolUseBlock, maps: ToolResultMaps): boolean {
  if (!toolBlockMatchesPreview(block)) {
    return false;
  }
  const result = findToolResult(block, maps);
  return result !== undefined && !result.isError;
}

function extractPresentedFilepaths(block: ToolUseBlock): string[] {
  const filepaths = block.argumentsJson?.filepaths;
  if (!Array.isArray(filepaths)) {
    return [];
  }
  return filepaths.filter((item): item is string => typeof item === "string");
}

export function deriveRenderableBlocks(
  blocks: ContentBlock[] | undefined,
  isStreaming: boolean
): RenderableContentBlock[] {
  const sourceBlocks = blocks || [];
  const toolResultMaps = buildToolResultMaps(sourceBlocks);
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

    const result = findToolResult(block, toolResultMaps);
    let status: ContentBlockRenderStatus;
    if (result) {
      status = result.isError ? ContentBlockRenderStatus.Error : ContentBlockRenderStatus.Success;
    } else if (hasNextRenderable || !isStreaming) {
      status = ContentBlockRenderStatus.Done;
    } else if (block.argumentsJson !== null) {
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

  const presentedFilepaths = sourceBlocks
    .filter(
      (block): block is ToolUseBlock => block.type === "tool_use" && isSuccessfulPreviewTool(block, toolResultMaps)
    )
    .flatMap(extractPresentedFilepaths);

  if (!isEmpty( presentedFilepaths)) {
    items.push({
      key: "project_preview",
      type: "project_preview",
      filepaths: presentedFilepaths,
    });
  }

  return items;
}
