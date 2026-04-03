import { ContentBlockRenderStatus, ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { Think } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import React, { useEffect, useMemo, useState } from "react";

import ToolArguments from "./ToolArguments";
import ToolBlockTitle from "./ToolBlockTitle";
import { getToolIcon } from "./toolIcons";
import { getResultLanguage, isActiveStatus, stringifyJsonLike } from "./utils";

type Props = {
  toolUseBlock: ToolUseBlock;
  toolResultBlock?: ToolResultBlock;
  status: ContentBlockRenderStatus;
};

export const ToolBlockRender: React.FC<Props> = ({ toolUseBlock, toolResultBlock, status }) => {
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

  const resultLanguage = useMemo(() => getResultLanguage(toolResultBlock?.content || ""), [toolResultBlock?.content]);

  return (
    <Think
      icon={getToolIcon(toolUseBlock.name)}
      expanded={expanded}
      blink={isActiveStatus(status)}
      onExpand={handleExpandChange}
      classNames={{ status: "cursor-pointer" }}
      title={<ToolBlockTitle rawToolName={toolUseBlock.name} status={status} />}
    >
      <div className="w-full flex flex-col gap-2 py-1">
        <ToolArguments argumentsText={toolUseBlock.argumentsText} />
        {toolResultBlock ? (
          toolResultBlock.isError ? (
            <div className="w-full flex items-start gap-2">
              <div className="whitespace-nowrap">tool call error.</div>
              {toolResultBlock.content ? <div>{toolResultBlock.content}</div> : null}
            </div>
          ) : (
            <CodeHighlighter
              lang={resultLanguage}
              header={"Result is"}
              styles={{
                code: { maxHeight: 300, width: "100%", overflow: "auto" },
              }}
            >
              {stringifyJsonLike(toolResultBlock.content || "")}
            </CodeHighlighter>
          )
        ) : null}
      </div>
    </Think>
  );
};

export default React.memo(ToolBlockRender);
