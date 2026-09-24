import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import React from "react";
import PreviewScrollBody from "../../../PreviewScrollBody";
import { isMarkdownPath } from "../../utils";
import FileSourceEditor from "./FileSourceEditor";
import { FileTitleBar } from "./PreviewModeShell";
import type { SelectedFile } from "./types";

const TextFilePreview: React.FC<{ file: SelectedFile; width: number }> = ({ file, width }) => {
  const layoutWidth = width > 0 ? width : 0;
  const isMarkdown = isMarkdownPath(file.path);

  return (
    <div className="h-full min-h-0 flex flex-col">
      <FileTitleBar title={file.title} />
      {isMarkdown ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <PreviewScrollBody width={layoutWidth}>
            <MarkdownContainer className="w-full text-base bg-white p-4">
              {file.content}
            </MarkdownContainer>
          </PreviewScrollBody>
        </div>
      ) : (
        <FileSourceEditor file={file} />
      )}
    </div>
  );
};

export default TextFilePreview;
