import React from "react";
import { isPlainObject } from "lodash-es";
import GrayContainer from "@/components/Chat/MarkdownContainer/components/GrayContainer";
import { ToolCallResultMessage } from "@/interfaces";
import { useMemo } from "react";
import NormalCode from "@/components/Chat/MarkdownContainer/components/NormalCode";

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

const ToolToolCallResultBlock = ({
  message,
}: {
  message: ToolCallResultMessage;
}) => {
  const { content } = message;
  const [contentStr, language] = useMemo(
    () => stringifyContentWithLanguage(content),
    [content]
  );

  return (
    <div className="w-full">
      <GrayContainer
        className="w-full"
        header={
          <div>
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
