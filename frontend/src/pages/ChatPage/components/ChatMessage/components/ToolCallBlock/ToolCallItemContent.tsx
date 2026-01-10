import { ToolCallStatus } from "@/constants";
import { TimelineMessage } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { prettyCount } from "@/utils/common";
import React, { useMemo } from "react";
import { stringifyArgs, stringifyContentWithLanguage } from "./utils";

type Props = {
  message: TimelineMessage;
};

const ToolCallItemContent: React.FC<Props> = ({ message }) => {
  const { status, reasoningContent, content } = message;
  const [contentStr, language] = useMemo(
    () => stringifyContentWithLanguage(content),
    [content]
  );

  return (
    <div className="w-full flex flex-col gap-2 py-1">
      <MarkdownContainer gray>{reasoningContent}</MarkdownContainer>
      <CodeHighlighter
        lang="json"
        header="parameters is:"
        styles={{ code: { maxHeight: 500, width: "100%", overflow: "auto" } }}
      >
        {stringifyArgs(message.toolCall.function.arguments)}
      </CodeHighlighter>
      {status === ToolCallStatus.ToolResultError && (
        <div className="w-full flex items-start gap-2">
          <div className="whitespace-nowrap">tool call error.</div>
          {contentStr && <div>{contentStr}</div>}
        </div>
      )}
      {status === ToolCallStatus.ToolResultSuccess && (
        <CodeHighlighter
          lang={language}
          header={[
            "result is:",
            message.tokenCount
              ? ` (${prettyCount(message.tokenCount)} tokens)`
              : "",
          ].filter(Boolean)}
          styles={{ code: { maxHeight: 300, width: "100%", overflow: "auto" } }}
        >
          {contentStr}
        </CodeHighlighter>
      )}
    </div>
  );
};

export default React.memo(ToolCallItemContent);
