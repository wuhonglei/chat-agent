import { Alert, Empty, Spin } from "antd";
import React from "react";
import type { ExcelSheet } from "../hooks";
import { isMermaidPath, isSvgPath } from "../utils";
import { isHtmlPath } from "../utils/sitePaths";
import WorkspaceExcelPreview from "./WorkspaceExcelPreview";
import WorkspaceImagePreview from "./WorkspaceImagePreview";
import BinaryFilePreview, { type BinaryFilePreviewProps } from "./filePreview/BinaryFilePreview";
import HtmlFilePreview from "./filePreview/HtmlFilePreview";
import MermaidFilePreview from "./filePreview/MermaidFilePreview";
import SvgFilePreview from "./filePreview/SvgFilePreview";
import TextFilePreview from "./filePreview/TextFilePreview";
import type { SelectedFile } from "./filePreview/types";

export type { SelectedFile };

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
  binaryFile?: BinaryFilePreviewProps | null;
  /** 已发布站点上对应当前 HTML 的公网 URL；有则预览走 iframe src，而不是 srcDoc。 */
  publishedPreviewUrl?: string | null;
}

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
    return <BinaryFilePreview {...binaryFile} />;
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

  if (isSvgPath(selectedFile.path)) {
    return <SvgFilePreview key={selectedFile.path} file={selectedFile} />;
  }

  if (isMermaidPath(selectedFile.path)) {
    return <MermaidFilePreview key={selectedFile.path} file={selectedFile} />;
  }

  return <TextFilePreview file={selectedFile} width={width} />;
};

export default React.memo(FilePreviewContent);
