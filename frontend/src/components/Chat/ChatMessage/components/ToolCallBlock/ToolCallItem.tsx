import React, { useMemo } from "react";
import { TimelineMessage } from "@/interfaces";
import { ToolCallStatus } from "@/constants";
import { Tag } from "antd";
import GrayContainer from "@/components/Chat/MarkdownContainer/components/GrayContainer";
import NormalCode from "@/components/Chat/MarkdownContainer/components/NormalCode";
import { isPlainObject } from "lodash-es";

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

function stringifyContentWithLanguage<T extends string | Record<string, any>>(
  content: T | undefined
): [string, string] {
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

const ToolCallItem: React.FC<Props> = ({ message }) => {
  const { status, content } = message;
  const [contentStr, language] = useMemo(
    () => stringifyContentWithLanguage(content),
    [content]
  );

  if (status === ToolCallStatus.AllFinished) {
    return (
      <div className="w-full flex items-center gap-2">
        <span>tool call finished.</span>
        {contentStr && <span>{contentStr}</span>}
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-2">
        <span className="font-bold">calling tool</span>
        <Tag color="processing" bordered={false} style={{ marginRight: 0 }}>
          {message.toolCall.function.name}
        </Tag>
        {"duration" in message && message.duration && (
          <span className="text-gray-600">{message.duration}s</span>
        )}
      </div>
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
        <div className="flex items-center gap-2">
          <span>tool call error</span>
          {contentStr && <span>{contentStr}</span>}
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
            style={{ maxHeight: 500, width: "100%" }}
          >
            {contentStr}
          </NormalCode>
        </GrayContainer>
      )}
    </div>
  );
};

export default React.memo(ToolCallItem);
