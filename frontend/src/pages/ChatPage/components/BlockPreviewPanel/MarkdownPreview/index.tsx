import type { MarkdownBlock } from "@/interfaces/contentBlock";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Spin, Tooltip, Typography } from "antd";
import { useRequest } from "ahooks";
import React from "react";
import PreviewScrollBody from "../PreviewScrollBody";

export interface MarkdownBlockPreviewPanelProps {
  width: number;
  block: MarkdownBlock;
  onClose: () => void;
}

const MARKDOWN_LOAD_ERROR = "Markdown 加载失败";

async function fetchMarkdownText(url: string): Promise<string> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  return res.text();
}

const MarkdownBlockPreviewPanel: React.FC<MarkdownBlockPreviewPanelProps> = ({ width, block, onClose }) => {
  const { url, name } = block;
  const layoutWidth = width > 0 ? width : 0;

  const {
    data: text,
    loading,
    error,
    refresh,
  } = useRequest(() => fetchMarkdownText(url), {
    refreshDeps: [url],
  });

  const errorMessage = error == null ? null : error instanceof Error ? error.message : MARKDOWN_LOAD_ERROR;

  const handleDownload = () => {
    downloadFileByUrl(url, name?.trim() || "document.md");
  };

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Typography.Text type="secondary">Markdown 预览</Typography.Text>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip title="下载 Markdown">
            <Button type="text" onClick={handleDownload} icon={<DownloadOutlined />} disabled={Boolean(errorMessage)} />
          </Tooltip>
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-auto">
        {loading ? (
          <div className="flex w-full justify-center py-12">
            <Spin />
          </div>
        ) : errorMessage ? (
          <div className="w-full py-8 text-center text-(--ant-color-error)">
            <Typography.Paragraph className="mb-3!">{errorMessage}</Typography.Paragraph>
            <Button type="default" onClick={refresh}>
              重新加载
            </Button>
          </div>
        ) : (
          <PreviewScrollBody width={layoutWidth}>
            <MarkdownContainer className="w-full text-base bg-white p-4">{text}</MarkdownContainer>
          </PreviewScrollBody>
        )}
      </div>
    </section>
  );
};

export default React.memo(MarkdownBlockPreviewPanel);
