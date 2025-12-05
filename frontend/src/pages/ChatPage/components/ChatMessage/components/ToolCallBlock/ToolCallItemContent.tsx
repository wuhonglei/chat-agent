import { ToolCallStatus } from "@/constants";
import { TimelineMessage } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { isPlainObject } from "lodash-es";
import React, { useMemo } from "react";

type Props = {
  message: TimelineMessage;
};

function stringifyArgs(args: string): string {
  if (!args) {
    return "";
  }

  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

function stringifyContentWithLanguage<
  T extends string | Record<string, unknown>,
>(content: T | undefined): [string, string] {
  if (!content) {
    return ["", ""];
  }

  if (isPlainObject(content)) {
    return [JSON.stringify(content, null, 2), "json"];
  }

  try {
    const str = JSON.stringify(JSON.parse(content as string), null, 2);
    return [str, "json"];
  } catch {
    return [content as string, "markdown"];
  }
}

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
          header={"result is:"}
          styles={{ code: { maxHeight: 300, width: "100%", overflow: "auto" } }}
        >
          {contentStr}
        </CodeHighlighter>
      )}
    </div>
  );
};

export default React.memo(ToolCallItemContent);
