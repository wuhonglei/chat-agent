import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Think } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import React, { useEffect, useMemo, useState } from "react";

type Props = {
  contentBlock: ToolUseBlock;
  result?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

const STATUS_TITLE_MAP: Record<ContentBlockRenderStatus, string> = {
  [ContentBlockRenderStatus.Start]: "工具准备中",
  [ContentBlockRenderStatus.Streaming]: "工具参数组装中",
  [ContentBlockRenderStatus.StreamFinished]: "工具参数已完成",
  [ContentBlockRenderStatus.Running]: "工具调用中",
  [ContentBlockRenderStatus.Success]: "工具调用成功",
  [ContentBlockRenderStatus.Error]: "工具调用失败",
  [ContentBlockRenderStatus.Done]: "工具调用结束",
};

const ACTIVE_STATUS_SET = new Set<ContentBlockRenderStatus>([
  ContentBlockRenderStatus.Start,
  ContentBlockRenderStatus.Streaming,
  ContentBlockRenderStatus.Running,
]);

function isActiveStatus(status: ContentBlockRenderStatus): boolean {
  return ACTIVE_STATUS_SET.has(status);
}

function stringifyJsonLike(input: string): string {
  if (!input) {
    return "";
  }
  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch {
    return input;
  }
}

function getResultLanguage(content: string): "json" | "markdown" {
  try {
    JSON.parse(content);
    return "json";
  } catch {
    return "markdown";
  }
}

export const ToolUseBlockRender: React.FC<Props> = ({ contentBlock, result, status }) => {
  const [expanded, setExpanded] = useState<boolean>(isActiveStatus(status));
  const handleExpandChange = useMemoizedFn((nextExpanded: boolean) => {
    setExpanded(nextExpanded);
  });

  useEffect(() => {
    if (isActiveStatus(status)) {
      setExpanded(true);
      return;
    }
    setExpanded(false);
  }, [status]);

  const displayToolName = contentBlock.name || "未知工具";
  const parsedArguments = useMemo(
    () => stringifyJsonLike(contentBlock.argumentsText || ""),
    [contentBlock.argumentsText]
  );
  const resultLanguage = useMemo(() => getResultLanguage(result?.content || ""), [result?.content]);

  return (
    <Think
      expanded={expanded}
      blink={isActiveStatus(status)}
      onExpand={handleExpandChange}
      title={`${displayToolName} · ${STATUS_TITLE_MAP[status] || "处理中"}`}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <CodeHighlighter
          lang="json"
          header="parameters"
          styles={{ code: { maxHeight: 500, width: "100%", overflow: "auto" } }}
        >
          {parsedArguments || "{}"}
        </CodeHighlighter>
        {result ? (
          result.isError ? (
            <div className="w-full flex items-start gap-2">
              <div className="whitespace-nowrap">tool call error.</div>
              {result.content ? <div>{result.content}</div> : null}
            </div>
          ) : (
            <CodeHighlighter
              lang={resultLanguage}
              header={["result", result.summary].filter(Boolean)}
              styles={{ code: { maxHeight: 300, width: "100%", overflow: "auto" } }}
            >
              {stringifyJsonLike(result.content || "")}
            </CodeHighlighter>
          )
        ) : null}
      </div>
    </Think>
  );
};

export default React.memo(ToolUseBlockRender);
