import { workspaceAPI } from "@/services";
import { useRequest } from "ahooks";
import { useEffect, useRef } from "react";
import * as XLSX from "xlsx";
import { getImageMimeType, getRequestErrorMessage } from "./utils";

const EXCEL_LOAD_ERROR = "Excel 加载失败";
const IMAGE_LOAD_ERROR = "图片加载失败";

export interface ExcelSheet {
  name: string;
  rows: string[][];
}

function normalizeCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

async function loadWorkspaceExcelSheets(workspaceId: string, path: string): Promise<ExcelSheet[]> {
  const buffer = await workspaceAPI.getWorkspaceFileBuffer(workspaceId, path);
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

export function useWorkspaceExcelWorkbook(workspaceId: string, path: string | null, enabled: boolean) {
  const ready = Boolean(enabled && path);

  const {
    data: sheets,
    loading,
    error,
    refresh,
  } = useRequest(() => loadWorkspaceExcelSheets(workspaceId, path!), {
    ready,
    refreshDeps: [workspaceId, path, enabled],
  });

  const errorMessage = error == null ? null : error instanceof Error ? error.message : EXCEL_LOAD_ERROR;

  return { sheets, loading, error: errorMessage, reload: refresh };
}

async function loadWorkspaceImageObjectUrl(workspaceId: string, path: string): Promise<string> {
  const buffer = await workspaceAPI.getWorkspaceFileBuffer(workspaceId, path);
  const blob = new Blob([buffer], { type: getImageMimeType(path) });
  return URL.createObjectURL(blob);
}

export function useWorkspaceImagePreview(workspaceId: string, path: string | null, enabled: boolean) {
  const ready = Boolean(enabled && path);
  const objectUrlRef = useRef<string | null>(null);

  const revokeCurrentUrl = () => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  };

  const {
    data: url,
    loading,
    error,
    refresh,
  } = useRequest(() => loadWorkspaceImageObjectUrl(workspaceId, path!), {
    ready,
    refreshDeps: [workspaceId, path, enabled],
    onBefore: () => {
      revokeCurrentUrl();
    },
    onSuccess: nextUrl => {
      objectUrlRef.current = nextUrl;
    },
    onError: () => {
      revokeCurrentUrl();
    },
  });

  useEffect(() => {
    if (!ready) {
      revokeCurrentUrl();
    }
  }, [ready]);

  useEffect(() => {
    return () => {
      revokeCurrentUrl();
    };
  }, []);

  const errorMessage = error == null ? null : getRequestErrorMessage(error, IMAGE_LOAD_ERROR);

  return {
    url: ready ? (url ?? null) : null,
    loading: ready && loading,
    error: ready ? errorMessage : null,
    reload: refresh,
  };
}
