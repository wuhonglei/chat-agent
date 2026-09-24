import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { DownloadOutlined } from "@ant-design/icons";
import Editor from "@monaco-editor/react";
import { Alert, Button, Empty, Segmented, Spin, Typography } from "antd";
import mermaid from "mermaid";
import React, { useEffect, useMemo, useRef, useState } from "react";
import PreviewScrollBody from "../../PreviewScrollBody";
import type { ExcelSheet } from "../hooks";
import { getDefaultHtmlViewMode, type HtmlViewMode } from "../utils/htmlPreview";
import { isHtmlPath } from "../utils/sitePaths";
import { getMonacoLanguage, isMarkdownPath, isMermaidPath, isSvgPath } from "../utils";
import WorkspaceExcelPreview from "./WorkspaceExcelPreview";
import WorkspaceImagePreview from "./WorkspaceImagePreview";

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

function toSvgDataUrl(content: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(content)}`;
}

const MermaidDiagram: React.FC<{ source: string }> = ({ source }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    let cancelled = false;
    setStatus("loading");
    setError(null);

    const renderId = `mmd-preview-${crypto.randomUUID()}`;
    void (async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "default",
        });
        const isValid = await mermaid.parse(source, { suppressErrors: true });
        if (!isValid) {
          throw new Error("Mermaid 语法无效");
        }
        const { svg } = await mermaid.render(renderId, source);
        if (cancelled) {
          return;
        }
        container.innerHTML = svg;
        const svgEl = container.querySelector("svg");
        if (svgEl) {
          const { width, height } = svgEl.viewBox.baseVal;
          if (width > 0 && height > 0) {
            svgEl.setAttribute("width", String(width));
            svgEl.setAttribute("height", String(height));
          }
          svgEl.style.maxWidth = "none";
          svgEl.style.maxHeight = "none";
        }
        setStatus("ready");
      } catch (err) {
        if (cancelled) {
          return;
        }
        container.innerHTML = "";
        setError(err instanceof Error ? err.message : "Mermaid 渲染失败");
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source]);

  return (
    <div className="relative min-h-0 flex-1 overflow-auto bg-(--ant-color-fill-quaternary)">
      {status === "loading" ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center">
          <Spin />
        </div>
      ) : null}
      {status === "error" ? <Alert type="error" showIcon message={error} className="m-4" /> : null}
      <div ref={containerRef} className={status === "ready" ? "inline-block p-4" : "hidden"} />
    </div>
  );
};

const MermaidFilePreview: React.FC<{ file: SelectedFile }> = ({ file }) => {
  const [userViewMode, setUserViewMode] = useState<HtmlViewMode | null>(null);
  const viewMode = userViewMode ?? "preview";
  const source = file.content.trim();

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
      {viewMode === "preview" ? (
        source ? (
          <MermaidDiagram source={source} />
        ) : (
          <Empty description="暂无可预览内容" className="m-auto" />
        )
      ) : (
        <FileSourceEditor file={file} />
      )}
    </div>
  );
};

const SvgFilePreview: React.FC<{ file: SelectedFile }> = ({ file }) => {
  const [userViewMode, setUserViewMode] = useState<HtmlViewMode | null>(null);
  const viewMode = userViewMode ?? "preview";
  const previewUrl = useMemo(() => toSvgDataUrl(file.content), [file.content]);

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
      {viewMode === "preview" ? (
        <div className="min-h-0 flex flex-1 items-center justify-center overflow-auto bg-(--ant-color-fill-quaternary) p-4">
          {file.content.trim() ? (
            <img
              src={previewUrl}
              alt={file.title}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <Empty description="暂无可预览内容" />
          )}
        </div>
      ) : (
        <FileSourceEditor file={file} />
      )}
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
        <Typography.Text
          type="secondary"
          className="px-3 py-2 border-b border-(--ant-color-border-secondary)"
        >
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

  if (isSvgPath(selectedFile.path)) {
    return <SvgFilePreview key={selectedFile.path} file={selectedFile} />;
  }

  if (isMermaidPath(selectedFile.path)) {
    return <MermaidFilePreview key={selectedFile.path} file={selectedFile} />;
  }

  const layoutWidth = width > 0 ? width : 0;
  const isMarkdown = isMarkdownPath(selectedFile.path);

  return (
    <div className="h-full min-h-0 flex flex-col">
      <Typography.Text
        type="secondary"
        className="px-3 py-2 border-b border-(--ant-color-border-secondary)"
      >
        {selectedFile.title}
      </Typography.Text>
      {isMarkdown ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <PreviewScrollBody width={layoutWidth}>
            <MarkdownContainer className="w-full text-base bg-white p-4">
              {selectedFile.content}
            </MarkdownContainer>
          </PreviewScrollBody>
        </div>
      ) : (
        <FileSourceEditor file={selectedFile} />
      )}
    </div>
  );
};

export default React.memo(FilePreviewContent);
