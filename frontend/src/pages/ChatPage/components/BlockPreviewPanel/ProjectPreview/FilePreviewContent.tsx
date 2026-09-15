import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import Editor from "@monaco-editor/react";
import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Segmented, Spin, Typography } from "antd";
import React, { useState } from "react";
import PreviewScrollBody from "../PreviewScrollBody";
import WorkspaceExcelPreview from "./WorkspaceExcelPreview";
import WorkspaceImagePreview from "./WorkspaceImagePreview";
import type { ExcelSheet } from "./hooks";
import { getDefaultHtmlViewMode, type HtmlViewMode } from "./htmlPreview";
import { getMonacoLanguage, isHtmlPath, isMarkdownPath } from "./utils";

const HTML_IFRAME_SANDBOX =
  "allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-presentation";

const PUBLISHED_HTML_IFRAME_SANDBOX =
  "allow-scripts allow-same-origin allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-pointer-lock allow-presentation allow-top-navigation-by-user-activation";

const SOURCE_EDITOR_OPTIONS = {
  readOnly: true,
  minimap: { enabled: false },
  wordWrap: "on" as const,
  scrollBeyondLastLine: false,
  automaticLayout: true,
  renderLineHighlight: "none" as const,
  padding: { top: 12, bottom: 12 },
};

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
  /** 已发布站点上对应当前 HTML 的公网 URL；有则预览走 iframe src，而不是 srcDoc。 */
  publishedPreviewUrl?: string | null;
}

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

const HtmlFilePreview: React.FC<{
  file: SelectedFile;
  publishedPreviewUrl?: string | null;
}> = ({ file, publishedPreviewUrl }) => {
  const defaultViewMode = getDefaultHtmlViewMode(file.content, publishedPreviewUrl);
  const [userViewMode, setUserViewMode] = useState<HtmlViewMode | null>(null);
  const viewMode = userViewMode ?? defaultViewMode;

  const previewFrame = publishedPreviewUrl ? (
    <iframe
      title={file.title}
      src={publishedPreviewUrl}
      sandbox={PUBLISHED_HTML_IFRAME_SANDBOX}
      className="h-full min-h-0 w-full flex-1 border-0 bg-white"
    />
  ) : (
    <iframe
      title={file.title}
      srcDoc={file.content}
      sandbox={HTML_IFRAME_SANDBOX}
      className="h-full min-h-0 w-full flex-1 border-0 bg-white"
    />
  );

  return (
    <div className="h-full min-h-0 flex flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) px-3 py-2">
        <Typography.Text type="secondary" className="min-w-0 truncate">
          {file.title}
        </Typography.Text>
        <Segmented<HtmlViewMode>
          size="small"
          value={viewMode}
          onChange={setUserViewMode}
          options={[
            { label: "预览", value: "preview" },
            { label: "源码", value: "source" },
          ]}
        />
      </div>
      {viewMode === "preview" ? previewFrame : <FileSourceEditor file={file} />}
    </div>
  );
};

const FilePreviewContent: React.FC<FilePreviewContentProps> = ({
  width,
  loadingFile,
  fileError,
  selectedFile,
  excelPreview,
  imagePreview,
  binaryFile,
  publishedPreviewUrl,
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

  if (isHtmlPath(selectedFile.path)) {
    return (
      <HtmlFilePreview
        key={selectedFile.path}
        file={selectedFile}
        publishedPreviewUrl={publishedPreviewUrl}
      />
    );
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
        <FileSourceEditor file={selectedFile} />
      )}
    </div>
  );
};

export default React.memo(FilePreviewContent);
