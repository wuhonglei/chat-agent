import { Empty } from "antd";
import React, { useMemo } from "react";
import FileSourceEditor from "./FileSourceEditor";
import PreviewModeShell from "./PreviewModeShell";
import type { SelectedFile } from "./types";

function toSvgDataUrl(content: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(content)}`;
}

const SvgFilePreview: React.FC<{ file: SelectedFile }> = ({ file }) => {
  const previewUrl = useMemo(() => toSvgDataUrl(file.content), [file.content]);
  const preview = (
    <div className="min-h-0 flex flex-1 items-center justify-center overflow-auto bg-(--ant-color-fill-quaternary) p-4">
      {file.content.trim() ? (
        <img src={previewUrl} alt={file.title} className="max-h-full max-w-full object-contain" />
      ) : (
        <Empty description="暂无可预览内容" />
      )}
    </div>
  );

  return (
    <PreviewModeShell
      title={file.title}
      preview={preview}
      source={<FileSourceEditor file={file} />}
    />
  );
};

export default SvgFilePreview;
