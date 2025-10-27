import React from "react";
import { isPlainObject } from "lodash-es";
import GrayContainer from "@/components/Chat/MarkdownContainer/components/GrayContainer";
import { ToolCallResultMessage } from "@/interfaces";
import { useMemo } from "react";
import NormalCode from "@/components/Chat/MarkdownContainer/components/NormalCode";
import { Tag } from "antd";

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

interface ToolToolCallResultBlockProps {
  message: ToolCallResultMessage;
}

const ToolToolCallResultBlock: React.FC<ToolToolCallResultBlockProps> = ({
  message,
}) => {
  const { content, toolCall } = message;
  const [contentStr, language] = useMemo(
    () => stringifyContentWithLanguage(content),
    [content]
  );

  return (
    <div className="w-full">
      <GrayContainer
        className="w-full"
        header={
          <div className="flex items-center gap-2">
            <Tag bordered={false} style={{ marginRight: 0 }}>
              {toolCall.function.name}
            </Tag>
            <span>result is:</span>
          </div>
        }
      >
        <NormalCode language={language} style={{ maxHeight: 500 }}>
          {contentStr}
        </NormalCode>
      </GrayContainer>
    </div>
  );
};

export default React.memo(ToolToolCallResultBlock);
