import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import Editor from "@monaco-editor/react";
import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Spin, Typography } from "antd";
import React from "react";
import PreviewScrollBody from "../PreviewScrollBody";
import WorkspaceExcelPreview from "./WorkspaceExcelPreview";
import WorkspaceImagePreview from "./WorkspaceImagePreview";
import type { ExcelSheet } from "./hooks";
import { getMonacoLanguage, isMarkdownPath } from "./utils";

export type SelectedFile = {
  path: string;
  title: string;
  content: string;
  language: string;
};

export interface FilePreviewContentProps {
  width: number;
  loadingFile: boolean;
  fileError: string | null;
  selectedFile: SelectedFile | null;
  excelPreview?: {
    title: string;
    sheets: ExcelSheet[] | undefined;
    loading: boolean;
    error: string | null;
  } | null;
  imagePreview?: {
    title: string;
    url: string | null;
    loading: boolean;
    error: string | null;
  } | null;
  binaryFile?: {
    title: string;
    message: string;
    downloading: boolean;
    onDownload: () => void;
  } | null;
}

const FilePreviewContent: React.FC<FilePreviewContentProps> = ({
  width,
  loadingFile,
  fileError,
  selectedFile,
  excelPreview,
  imagePreview,
  binaryFile,
}) => {
  if (excelPreview) {
    return (
      <WorkspaceExcelPreview
        title={excelPreview.title}
        sheets={excelPreview.sheets}
        loading={excelPreview.loading}
        error={excelPreview.error}
      />
    );
  }
  if (imagePreview) {
    return (
      <WorkspaceImagePreview
        title={imagePreview.title}
        url={imagePreview.url}
        loading={imagePreview.loading}
        error={imagePreview.error}
      />
    );
  }
  if (binaryFile) {
    return (
      <div className="h-full min-h-0 flex flex-col">
        <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
          {binaryFile.title}
        </Typography.Text>
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
          <Alert type="info" showIcon message={binaryFile.message} className="max-w-md" />
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={binaryFile.downloading}
            onClick={binaryFile.onDownload}
          >
            下载文件
          </Button>
        </div>
      </div>
    );
  }
  if (loadingFile) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <Spin />
      </div>
    );
  }
  if (fileError) {
    return <Alert type="error" showIcon message={fileError} />;
  }
  if (!selectedFile) {
    return <Empty description="请选择左侧文件查看内容" className="mt-12" />;
  }

  const layoutWidth = width > 0 ? width : 0;
  const isMarkdown = isMarkdownPath(selectedFile.path);

  return (
    <div className="h-full min-h-0 flex flex-col">
      <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
        {selectedFile.title}
      </Typography.Text>
      {isMarkdown ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <PreviewScrollBody width={layoutWidth}>
            <MarkdownContainer className="w-full text-base bg-white p-4">{selectedFile.content}</MarkdownContainer>
          </PreviewScrollBody>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-hidden">
          <Editor
            height="100%"
            language={getMonacoLanguage(selectedFile.language)}
            value={selectedFile.content}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              renderLineHighlight: "none",
              padding: { top: 12, bottom: 12 },
            }}
          />
        </div>
      )}
    </div>
  );
};

export default React.memo(FilePreviewContent);
