import { Empty, Spin, Tabs, Typography } from "antd";
import React, { useMemo } from "react";
import type { ExcelSheet } from "./hooks";

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

export interface WorkspaceExcelPreviewProps {
  title: string;
  sheets: ExcelSheet[] | undefined;
  loading: boolean;
  error: string | null;
}

const WorkspaceExcelPreview: React.FC<WorkspaceExcelPreviewProps> = ({ title, sheets, loading, error }) => {
  const tabItems = useMemo(
    () =>
      (sheets ?? []).map((sheet, index) => ({
        key: `${index}-${sheet.name}`,
        label: sheet.name,
        children: <SheetTable sheet={sheet} />,
      })),
    [sheets]
  );

  return (
    <div className="h-full min-h-0 flex flex-col">
      <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
        {title}
      </Typography.Text>
      <div className="min-h-0 flex-1 overflow-auto p-3">
        {loading ? (
          <div className="flex w-full justify-center py-12">
            <Spin />
          </div>
        ) : error ? (
          <Typography.Paragraph className="text-center text-(--ant-color-error)">{error}</Typography.Paragraph>
        ) : tabItems.length === 0 ? (
          <Empty description="暂无可预览内容" />
        ) : (
          <Tabs size="small" items={tabItems} />
        )}
      </div>
    </div>
  );
};

export default React.memo(WorkspaceExcelPreview);
