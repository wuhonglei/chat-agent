import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import React from "react";

import { getLanguageFromFilePath } from "../utils/filePathLanguage";

const containerStyle = { maxHeight: 300, width: "100%", overflow: "auto" };

type FileContentHighlightProps = {
  filePath: string | undefined;
  content: string;
  header?: string;
};

function getDefaultHeader(filePath: string | undefined): string {
  return filePath || "File content";
}

export function FileContentHighlight({
  filePath,
  content,
  header,
}: FileContentHighlightProps): React.ReactNode {
  const language = (filePath && getLanguageFromFilePath(filePath)) || "text";

  return (
    <CodeHighlighter
      lang={language}
      header={header ?? getDefaultHeader(filePath)}
      styles={{
        code: containerStyle,
      }}
    >
      {content}
    </CodeHighlighter>
  );
}
