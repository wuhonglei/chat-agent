import { ToolCallStatus } from "@/constants";
import { TimelineMessage } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import GrayContainer from "@/pages/ChatPage/components/MarkdownContainer/components/GrayContainer";
import NormalCode from "@/pages/ChatPage/components/MarkdownContainer/components/NormalCode";
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
    <div className="w-full flex flex-col gap-2">
      <MarkdownContainer className="mt-1">{reasoningContent}</MarkdownContainer>
      <GrayContainer
        className="flex flex-col gap-1 items-start w-full"
        header={
          <div className="flex items-center gap-2">
            <span>parameters is:</span>
          </div>
        }
      >
        <NormalCode language="json" style={{ maxHeight: 500, width: "100%" }}>
          {stringifyArgs(message.toolCall.function.arguments)}
        </NormalCode>
      </GrayContainer>
      {status === ToolCallStatus.ToolResultError && (
        <div className="w-full flex items-start gap-2">
          <div className="whitespace-nowrap">tool call error.</div>
          {contentStr && <div>{contentStr}</div>}
        </div>
      )}
      {status === ToolCallStatus.ToolResultSuccess && (
        <GrayContainer
          className="flex flex-col gap-1 items-start w-full"
          header={
            <div className="flex items-center gap-2">
              <span>result is:</span>
            </div>
          }
        >
          <NormalCode
            language={language}
            style={{ maxHeight: 300, width: "100%" }}
          >
            {contentStr}
          </NormalCode>
        </GrayContainer>
      )}
    </div>
  );
};

export default React.memo(ToolCallItemContent);
