import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { ToolOutlined } from "@ant-design/icons";
import { Think } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import React, { useEffect, useMemo, useState } from "react";

import { STATUS_TITLE_MAP } from "./constants";
import { useParsedArguments } from "./hooks";
import { getResultLanguage, isActiveStatus, stringifyJsonLike } from "./utils";

type Props = {
  contentBlock: ToolUseBlock;
  result?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

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
  const { parsedArguments, argumentsLanguage } = useParsedArguments(contentBlock);
  const resultLanguage = useMemo(() => getResultLanguage(result?.content || ""), [result?.content]);

  return (
    <Think
      icon={<ToolOutlined />}
      expanded={expanded}
      blink={isActiveStatus(status)}
      onExpand={handleExpandChange}
      title={`${displayToolName} · ${STATUS_TITLE_MAP[status] || "处理中"}`}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <CodeHighlighter
          header="parameters"
          lang={argumentsLanguage}
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
              header={"Result is"}
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
