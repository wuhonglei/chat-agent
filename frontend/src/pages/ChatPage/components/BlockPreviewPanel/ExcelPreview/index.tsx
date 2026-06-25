import type { ExcelBlock } from "@/interfaces/contentBlock";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { downloadFileByUrl } from "@/utils";
import { Button, Empty, Spin, Tabs, Typography } from "antd";
import React, { useEffect, useMemo, useState } from "react";
import PreviewScrollBody from "../PreviewScrollBody";
import { useMarkdownPreviewContent } from "../PdfPreview/hooks";
import ExcelPreviewHeader, { type PreviewMode } from "./ExcelPreviewHeader";
import { useExcelWorkbook, type ExcelSheet } from "./hooks";

export interface ExcelBlockPreviewPanelProps {
  /** 侧栏宽度（px），用于 padding */
  width: number;
  block: ExcelBlock;
  onClose: () => void;
}

const SheetTable: React.FC<{ sheet: ExcelSheet }> = ({ sheet }) => {
  if (sheet.rows.length === 0) {
    return <Empty description="空工作表" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const [headerRow, ...bodyRows] = sheet.rows;

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

const ExcelBlockPreviewPanel: React.FC<ExcelBlockPreviewPanelProps> = ({ width, block, onClose }) => {
  const { url: excelUrl, name: excelName, markdown: markdownBlock } = block;
  const layoutWidth = width > 0 ? width : 0;

  const hasMarkdown = Boolean(markdownBlock?.url);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("table");

  const isMarkdownView = hasMarkdown && previewMode === "markdown";
  const isTableView = !isMarkdownView;

  const {
    sheets,
    loading: sheetsLoading,
    error: sheetsError,
    reload: reloadSheets,
  } = useExcelWorkbook(excelUrl, isTableView);

  const markdownUrl = markdownBlock?.url;
  const {
    text: markdownText,
    loading: markdownLoading,
    error: markdownError,
    reload: reloadMarkdown,
  } = useMarkdownPreviewContent(markdownUrl, isMarkdownView);

  useEffect(() => {
    setPreviewMode("table");
  }, [block.id, excelUrl]);

  const tabItems = useMemo(
    () =>
      (sheets ?? []).map((sheet, index) => ({
        key: `${index}-${sheet.name}`,
        label: sheet.name,
        children: <SheetTable sheet={sheet} />,
      })),
    [sheets]
  );

  const sheetCount = sheets?.length ?? 0;

  const handleDownload = () => {
    if (previewMode === "markdown" && markdownBlock?.url) {
      downloadFileByUrl(markdownBlock.url, markdownBlock.name?.trim() || "spreadsheet.md");
    } else {
      downloadFileByUrl(excelUrl, excelName?.trim() || "spreadsheet.xlsx");
    }
  };

  const downloadDisabled = previewMode === "markdown" ? Boolean(markdownError) : Boolean(sheetsError);

  const tableErrorFallback = sheetsError ? (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{sheetsError}</Typography.Paragraph>
      <Button type="default" onClick={reloadSheets}>
        重新加载
      </Button>
    </div>
  ) : null;

  const markdownErrorFallback = markdownError ? (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{markdownError}</Typography.Paragraph>
      <Button type="default" onClick={reloadMarkdown}>
        重新加载
      </Button>
    </div>
  ) : null;

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <ExcelPreviewHeader
        onClose={onClose}
        sheetCount={sheetCount}
        hasMarkdown={hasMarkdown}
        previewMode={previewMode}
        onDownload={handleDownload}
        onPreviewModeChange={setPreviewMode}
        downloadDisabled={downloadDisabled}
      />
      <div className="flex-1 min-h-0 overflow-auto">
        {isMarkdownView ? (
          <PreviewScrollBody width={layoutWidth}>
            {markdownLoading ? (
              <div className="flex w-full justify-center py-12">
                <Spin />
              </div>
            ) : markdownErrorFallback ? (
              markdownErrorFallback
            ) : (
              <MarkdownContainer className="w-full text-base bg-white p-4">{markdownText}</MarkdownContainer>
            )}
          </PreviewScrollBody>
        ) : (
          <PreviewScrollBody width={layoutWidth}>
            {sheetsLoading ? (
              <div className="flex w-full justify-center py-12">
                <Spin />
              </div>
            ) : tableErrorFallback ? (
              tableErrorFallback
            ) : tabItems.length === 0 ? (
              <Empty description="暂无可预览内容" />
            ) : (
              <Tabs size="small" items={tabItems} />
            )}
          </PreviewScrollBody>
        )}
      </div>
    </section>
  );
};

export default React.memo(ExcelBlockPreviewPanel);
