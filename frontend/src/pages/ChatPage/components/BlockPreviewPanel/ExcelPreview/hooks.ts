import { useRequest } from "ahooks";
import * as XLSX from "xlsx";

const EXCEL_LOAD_ERROR = "Excel 加载失败";

export interface ExcelSheet {
  name: string;
  /** 行数据（数组的数组），第一行通常为表头 */
  rows: string[][];
}

function normalizeCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

async function fetchWorkbookSheets(url: string): Promise<ExcelSheet[]> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  const buffer = await res.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  return workbook.SheetNames.map(name => {
    const worksheet = workbook.Sheets[name];
    const matrix = XLSX.utils.sheet_to_json<unknown[]>(worksheet, {
      header: 1,
      blankrows: false,
      defval: "",
    });
    const rows = matrix.map(row => row.map(normalizeCell));
    return { name, rows };
  });
}

export function useExcelWorkbook(url: string | undefined, enabled: boolean) {
  const ready = Boolean(enabled && url);

  const {
    data: sheets,
    loading,
    error,
    refresh,
  } = useRequest(() => fetchWorkbookSheets(url!), {
    ready,
    refreshDeps: [url, enabled],
  });

  const errorMessage = error == null ? null : error instanceof Error ? error.message : EXCEL_LOAD_ERROR;

  return { sheets, loading, error: errorMessage, reload: refresh };
}
