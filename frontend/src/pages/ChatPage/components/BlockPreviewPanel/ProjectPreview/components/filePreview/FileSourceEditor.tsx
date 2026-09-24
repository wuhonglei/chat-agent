import Editor from "@monaco-editor/react";
import React from "react";
import { getMonacoLanguage } from "../../utils";
import type { SelectedFile } from "./types";

const SOURCE_EDITOR_OPTIONS = {
  readOnly: true,
  minimap: { enabled: false },
  wordWrap: "on" as const,
  scrollBeyondLastLine: false,
  automaticLayout: true,
  renderLineHighlight: "none" as const,
  padding: { top: 12, bottom: 12 },
};

const FileSourceEditor: React.FC<{ file: SelectedFile }> = ({ file }) => {
  return (
    <div className="min-h-0 flex-1 overflow-hidden">
      <Editor
        height="100%"
        language={getMonacoLanguage(file.language)}
        value={file.content}
        options={SOURCE_EDITOR_OPTIONS}
      />
    </div>
  );
};

export default FileSourceEditor;
