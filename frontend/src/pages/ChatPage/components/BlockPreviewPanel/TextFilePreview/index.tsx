import type { TextFileBlock } from "@/interfaces/contentBlock";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import { getLanguageFromFilePath } from "@/pages/ChatPage/components/ChatMessage/AssistantMessage/ContentBlocksRender/ToolBlockRender/registry/utils/filePathLanguage";
import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Empty, Spin, Tooltip, Typography } from "antd";
import React, { useMemo } from "react";
import PreviewScrollBody from "../PreviewScrollBody";
import { parseDelimitedToRows, useTextFileContent } from "./hooks";

export interface TextFileBlockPreviewPanelProps {
  /** 侧栏宽度（px），用于 padding */
  width: number;
  block: TextFileBlock;
  onClose: () => void;
}

function getExtension(name: string | undefined): string {
  return name?.split(".").pop()?.toLowerCase() ?? "";
}

const CsvTable: React.FC<{ rows: string[][] }> = ({ rows }) => {
  if (rows.length === 0) {
    return <Empty description="空文件" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const [headerRow, ...bodyRows] = rows;

  return (
    <div className="w-full overflow-auto rounded-md border border-(--ant-color-border-secondary) bg-white">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {headerRow.map((cell, colIndex) => (
              <th
                key={colIndex}
                className="border border-(--ant-color-border-secondary) bg-(--ant-color-fill-tertiary) px-3 py-2 text-left font-medium whitespace-nowrap"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headerRow.map((_, colIndex) => (
                <td
                  key={colIndex}
                  className="border border-(--ant-color-border-secondary) px-3 py-2 align-top whitespace-pre-wrap"
                >
                  {row[colIndex] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const TextFileBlockPreviewPanel: React.FC<TextFileBlockPreviewPanelProps> = ({
  width,
  block,
  onClose,
}) => {
  const { url, name } = block;
  const layoutWidth = width > 0 ? width : 0;
  const ext = getExtension(name);
  const isTable = ext === "csv" || ext === "tsv";

  const { text, loading, error, reload } = useTextFileContent(url, true);

  const tableRows = useMemo(() => {
    if (!isTable || text == null) {
      return null;
    }
    try {
      return parseDelimitedToRows(text, ext === "tsv" ? "\t" : ",");
    } catch {
      return [];
    }
  }, [isTable, ext, text]);

  const language = useMemo(() => getLanguageFromFilePath(name ?? "") ?? "text", [name]);

  const handleDownload = () => {
    downloadFileByUrl(url, name?.trim() || "file.txt");
  };

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Typography.Text type="secondary" ellipsis>
            {name?.trim() || "文本预览"}
          </Typography.Text>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip title="下载文件">
            <Button
              type="text"
              onClick={handleDownload}
              icon={<DownloadOutlined />}
              disabled={Boolean(error)}
            />
          </Tooltip>
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-auto">
        {loading ? (
          <div className="flex w-full justify-center py-12">
            <Spin />
          </div>
        ) : error ? (
          <div className="w-full py-8 text-center text-(--ant-color-error)">
            <Typography.Paragraph className="mb-3!">{error}</Typography.Paragraph>
            <Button type="default" onClick={reload}>
              重新加载
            </Button>
          </div>
        ) : isTable ? (
          <PreviewScrollBody width={layoutWidth}>
            <CsvTable rows={tableRows ?? []} />
          </PreviewScrollBody>
        ) : (
          <PreviewScrollBody width={layoutWidth}>
            <CodeHighlighter
              header={null}
              lang={language}
              maxHeight={null}
              styles={{ code: { width: "100%" } }}
            >
              {text ?? ""}
            </CodeHighlighter>
          </PreviewScrollBody>
        )}
      </div>
    </section>
  );
};

export default React.memo(TextFileBlockPreviewPanel);
