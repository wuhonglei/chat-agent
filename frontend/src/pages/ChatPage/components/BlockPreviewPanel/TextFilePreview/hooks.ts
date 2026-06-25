import { useRequest } from "ahooks";
import * as XLSX from "xlsx";

const TEXT_LOAD_ERROR = "文件加载失败";

export interface CsvTable {
  /** 行数据（数组的数组），第一行通常为表头 */
  rows: string[][];
}

function normalizeCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

async function fetchTextContent(url: string): Promise<string> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  return res.text();
}

export function useTextFileContent(url: string | undefined, enabled: boolean) {
  const ready = Boolean(enabled && url);

  const {
    data: text,
    loading,
    error,
    refresh,
  } = useRequest(() => fetchTextContent(url!), {
    ready,
    refreshDeps: [url, enabled],
  });

  const errorMessage = error == null ? null : error instanceof Error ? error.message : TEXT_LOAD_ERROR;

  return { text, loading, error: errorMessage, reload: refresh };
}

/** 将分隔值文本（CSV/TSV）解析为表格行（复用 SheetJS 的字符串解析能力）。 */
export function parseDelimitedToRows(text: string, delimiter: string = ","): string[][] {
  const workbook = XLSX.read(text, { type: "string", FS: delimiter });
  const firstSheetName = workbook.SheetNames[0];
  if (!firstSheetName) {
    return [];
  }
  const worksheet = workbook.Sheets[firstSheetName];
  const matrix = XLSX.utils.sheet_to_json<unknown[]>(worksheet, {
    header: 1,
    blankrows: false,
    defval: "",
  });
  return matrix.map(row => row.map(normalizeCell));
}
